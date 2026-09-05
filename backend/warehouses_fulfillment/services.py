"""Warehouse Split Optimizer (spec §7.2).

`optimize_split` is deliberately framework-agnostic — plain dataclasses in, plain
dataclasses out, no Django imports — so the allocation rule is unit-testable on its own
and can run from a view, a signal or a Celery task. Everything below it is the Django
adapter layer: it loads stock, writes `warehouse_split_line` rows, holds the stock
reservations and enforces the "cannot oversell, even via override" rule.
"""

from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from typing import Sequence

from django.db import models, transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from audit_log.models import record

from .models import (
    BackorderEvent,
    FulfillmentOrder,
    StockLevel,
    Warehouse,
    WarehouseSplitLine,
)

ZERO = Decimal("0.00")

# How far out we promise delivery. A clean split ships from stock on hand; a backordered
# order has to wait on replenishment, so it gets the longer promise. Both feed the
# delivery-slippage alert in Deal Health (§5.7).
LEAD_DAYS_IN_STOCK = 7
LEAD_DAYS_BACKORDER = 21


# --------------------------------------------------------------------------------------
# The engine (§7.2 steps 1-4) — no Django, no I/O.
# --------------------------------------------------------------------------------------


@dataclass(frozen=True)
class WarehouseStock:
    """One warehouse's availability for a single product, as the engine sees it."""

    warehouse_id: str
    shipping_cost_weight: Decimal
    qty_available: Decimal


@dataclass(frozen=True)
class Allocation:
    warehouse_id: str
    qty: Decimal
    cost: Decimal
    est_shipment_count: int
    is_backorder: bool


@dataclass(frozen=True)
class ProductPlan:
    product_id: str
    qty_needed: Decimal
    allocations: Sequence[Allocation]

    @property
    def qty_allocated(self) -> Decimal:
        return sum((a.qty for a in self.allocations if not a.is_backorder), ZERO)

    @property
    def shortfall(self) -> Decimal:
        return sum((a.qty for a in self.allocations if a.is_backorder), ZERO)

    @property
    def is_backorder(self) -> bool:
        return self.shortfall > ZERO


def _q2(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _by_cost(stocks: Sequence[WarehouseStock]):
    """Step 1 — cheapest/preferred first. `warehouse_id` is the tie-breaker purely so the
    suggestion is stable between runs when two sites share a weight."""
    return sorted(stocks, key=lambda s: (Decimal(s.shipping_cost_weight), str(s.warehouse_id)))


def optimize_split(
    product_id: str, qty_needed: Decimal, stocks: Sequence[WarehouseStock]
) -> ProductPlan:
    """Allocate `qty_needed` of one product across warehouses.

    1. Sort by `shipping_cost_weight` ascending.
    2. Try a single warehouse that can cover the whole line — one shipment beats a
       marginally cheaper two-shipment split.
    3. Otherwise allocate greedily cheapest → next cheapest until satisfied.
    4. Anything still short becomes a final `is_backorder=True` line.
    """
    qty_needed = _q2(qty_needed)
    ordered = _by_cost(stocks)

    def line(stock, qty, is_backorder=False):
        return Allocation(
            warehouse_id=stock.warehouse_id,
            qty=_q2(qty),
            # Cost is the relative shipping weight applied to the units moved — the
            # number step 2 is trading a second shipment against.
            cost=_q2(Decimal(stock.shipping_cost_weight) * Decimal(qty)),
            est_shipment_count=0 if is_backorder else 1,
            is_backorder=is_backorder,
        )

    if qty_needed <= ZERO:
        return ProductPlan(product_id=product_id, qty_needed=qty_needed, allocations=())

    # Step 2: single-warehouse fulfilment, cheapest site that can cover it alone.
    for stock in ordered:
        if Decimal(stock.qty_available) >= qty_needed:
            return ProductPlan(
                product_id=product_id,
                qty_needed=qty_needed,
                allocations=(line(stock, qty_needed),),
            )

    # Step 3: greedy cheapest → next cheapest.
    remaining = qty_needed
    allocations = []
    for stock in ordered:
        if remaining <= ZERO:
            break
        take = min(remaining, max(ZERO, _q2(stock.qty_available)))
        if take <= ZERO:
            continue
        allocations.append(line(stock, take))
        remaining -= take

    # Step 4: the shortfall becomes its own backorder line. It is booked against the
    # cheapest warehouse — the site we would rather ship from once stock returns, and the
    # one the consolidation watcher then compares incoming stock against.
    if remaining > ZERO and ordered:
        allocations.append(line(ordered[0], remaining, is_backorder=True))

    return ProductPlan(
        product_id=product_id, qty_needed=qty_needed, allocations=tuple(allocations)
    )


# --------------------------------------------------------------------------------------
# Django adapter
# --------------------------------------------------------------------------------------


def quotation_demand(quotation):
    """Units needed per product. Aggregated because one quote can carry the same product
    on two lines (different variants), but stock is only ever held per product."""
    demand = {}
    for line in quotation.lines.select_related("product"):
        demand[line.product] = demand.get(line.product, ZERO) + Decimal(line.qty)
    return demand


def _stock_map(company, products, lock=False):
    """Current availability keyed (product_id, warehouse_id), with a row created on the
    fly for any product a warehouse has never stocked so allocation sees an explicit 0."""
    warehouses = list(Warehouse.objects.filter(company=company))
    levels = {}
    for warehouse in warehouses:
        for product in products:
            level, _ = StockLevel.objects.get_or_create(warehouse=warehouse, product=product)
            levels[(product.id, warehouse.id)] = level
    if lock:
        # Re-read under a row lock so two concurrent accepts can't both pass validation
        # against the same units.
        locked = StockLevel.objects.select_for_update().filter(
            id__in=[level.id for level in levels.values()]
        )
        by_id = {level.id: level for level in locked}
        levels = {key: by_id[level.id] for key, level in levels.items()}
    return warehouses, levels


def _stocks_for(product, warehouses, levels):
    return [
        WarehouseStock(
            warehouse_id=warehouse.id,
            shipping_cost_weight=warehouse.shipping_cost_weight,
            qty_available=levels[(product.id, warehouse.id)].qty_available,
        )
        for warehouse in warehouses
    ]


def plan_for_quotation(quotation):
    """Run the optimiser over every product on a quote. Read-only — writes nothing."""
    demand = quotation_demand(quotation)
    warehouses, levels = _stock_map(quotation.company, demand.keys())
    return [
        (product, optimize_split(product.id, qty, _stocks_for(product, warehouses, levels)))
        for product, qty in demand.items()
    ]


def _release_reservations(order):
    """Hand every unit this order is holding back to the pool. Called before re-planning
    or overriding so validation always compares against a clean `qty_available` instead of
    fighting the order's own reservation."""
    if order.status not in FulfillmentOrder.RESERVED_STATUSES:
        return
    for line in order.split_lines.filter(is_backorder=False):
        level = StockLevel.objects.filter(
            warehouse_id=line.warehouse_id, product_id=line.product_id
        ).first()
        if level:
            level.release(line.qty_fulfilled)


def _sync_backorder_event(order, actor, note=""):
    """Open an event when the order first goes short, close the open one when it doesn't.
    Kept separate from the split rows because a backorder is a lifecycle, not a flag."""
    open_event = order.open_backorder_event
    if order.has_backorder:
        if open_event is None:
            return BackorderEvent.objects.create(fulfillment_order=order, resolution_note=note)
        return open_event
    if open_event is not None:
        open_event.resolved = True
        open_event.resolution_note = note or "All lines allocated from available stock."
        open_event.save(update_fields=["resolved", "resolution_note"])
    return None


def _promised_date(has_backorder):
    days = LEAD_DAYS_BACKORDER if has_backorder else LEAD_DAYS_IN_STOCK
    return (timezone.now() + timedelta(days=days)).date()


@transaction.atomic
def build_suggested_split(order, actor=None):
    """(Re)write the suggested split for an order. Suggestion only — nothing is reserved
    until Finance accepts or overrides, so a suggestion never blocks stock."""
    quotation = order.quotation
    order.split_lines.all().delete()

    for product, plan in plan_for_quotation(quotation):
        for allocation in plan.allocations:
            WarehouseSplitLine.objects.create(
                fulfillment_order=order,
                warehouse_id=allocation.warehouse_id,
                product=product,
                qty_fulfilled=allocation.qty,
                est_shipment_count=allocation.est_shipment_count,
                cost=allocation.cost,
                is_backorder=allocation.is_backorder,
            )

    order.status = FulfillmentOrder.SUGGESTED
    order.promised_date = _promised_date(order.has_backorder)
    order.save(update_fields=["status", "promised_date", "updated_at"])
    _sync_backorder_event(order, actor, note="Raised by the split optimiser at suggestion time.")
    return order


def ensure_fulfillment_order(quotation, actor=None):
    """Idempotent entry point used by the approval/confirmation trigger (§11).

    A quote that is already accepted or overridden is left alone — re-approving a deal
    must never silently throw away a split Finance has already signed off and reserved.
    """
    if not Warehouse.objects.filter(company=quotation.company).exists():
        # No warehouses configured for the tenant yet; nothing meaningful to plan.
        return None

    order, created = FulfillmentOrder.objects.get_or_create(quotation=quotation)
    if created or order.status == FulfillmentOrder.SUGGESTED:
        build_suggested_split(order, actor)
        if created:
            record(
                quotation.company,
                actor,
                quotation,
                "fulfillment_order_opened",
                reason=f"Quotation reached '{quotation.status}'; split optimiser ran.",
                fulfillment_order_id=str(order.id),
                shipment_count=order.shipment_count,
                has_backorder=order.has_backorder,
            )
    return order


# --------------------------------------------------------------------------------------
# Accept / override (§7.2.5)
# --------------------------------------------------------------------------------------


def _reserve_plan(allocations, levels):
    """Validate every requested quantity against live `qty_available` and reserve it.

    This is the single choke point that makes overselling impossible: the suggested split
    and a manual override both come through here, so a hand-typed quantity gets exactly
    the same server-side check as an engine-produced one (§7.2.5).
    """
    errors = []
    for warehouse, product, qty in allocations:
        level = levels[(product.id, warehouse.id)]
        if Decimal(qty) > level.qty_available:
            errors.append(
                f"{product.name}: {_q2(qty)} requested from {warehouse.name}, "
                f"only {_q2(level.qty_available)} available."
            )
    if errors:
        raise ValidationError({"detail": "Cannot oversell stock.", "lines": errors})

    for warehouse, product, qty in allocations:
        if Decimal(qty) > ZERO:
            levels[(product.id, warehouse.id)].reserve(qty)


@transaction.atomic
def accept_split(order, actor):
    """Take the suggestion as-is and reserve the stock behind it."""
    if order.status in {FulfillmentOrder.FULFILLED, FulfillmentOrder.CANCELLED}:
        raise ValidationError({"detail": f"A {order.get_status_display()} order cannot change."})

    _release_reservations(order)

    lines = list(order.split_lines.select_related("warehouse", "product"))
    products = {line.product for line in lines}
    _, levels = _stock_map(order.quotation.company, products, lock=True)

    _reserve_plan(
        [
            (line.warehouse, line.product, line.qty_fulfilled)
            for line in lines
            if not line.is_backorder
        ],
        levels,
    )

    order.status = (
        FulfillmentOrder.BACKORDERED if order.has_backorder else FulfillmentOrder.ACCEPTED
    )
    order.promised_date = _promised_date(order.has_backorder)
    order.save(update_fields=["status", "promised_date", "updated_at"])
    _sync_backorder_event(order, actor)

    record(
        order.quotation.company,
        actor,
        order.quotation,
        "fulfillment_split_accepted",
        reason="Suggested warehouse split accepted; stock reserved.",
        fulfillment_order_id=str(order.id),
        shipment_count=order.shipment_count,
        has_backorder=order.has_backorder,
    )
    return order


@transaction.atomic
def override_split(order, actor, allocations, reason=""):
    """Manual Override — Finance/Ops types the per-warehouse quantities themselves.

    `allocations` is a list of {warehouse, product, qty}. The totals must still match the
    quotation's demand, and every quantity is validated against live `qty_available`; a
    shortfall the user leaves unallocated is written as a backorder line exactly as the
    engine would (§7.2.4-5).
    """
    if order.status in {FulfillmentOrder.FULFILLED, FulfillmentOrder.CANCELLED}:
        raise ValidationError({"detail": f"A {order.get_status_display()} order cannot change."})

    demand = quotation_demand(order.quotation)
    demand_by_id = {product.id: qty for product, qty in demand.items()}
    products_by_id = {product.id: product for product in demand}

    requested = {}
    for entry in allocations:
        product = products_by_id.get(entry["product"].id)
        if product is None:
            raise ValidationError(
                {"detail": f"{entry['product'].name} is not on quotation {order.quotation.number}."}
            )
        if Decimal(entry["qty"]) < ZERO:
            raise ValidationError({"detail": "Quantities cannot be negative."})
        key = (product.id, entry["warehouse"].id)
        # Two rows for the same warehouse/product would each pass the availability check
        # on their own but oversell together, so they are merged before validating.
        requested[key] = requested.get(key, ZERO) + Decimal(entry["qty"])

    per_product = {}
    for (product_id, _), qty in requested.items():
        per_product[product_id] = per_product.get(product_id, ZERO) + qty
    for product_id, needed in demand_by_id.items():
        allocated = per_product.get(product_id, ZERO)
        if allocated > needed:
            raise ValidationError(
                {
                    "detail": (
                        f"{products_by_id[product_id].name}: {_q2(allocated)} allocated but the "
                        f"quotation only calls for {_q2(needed)}."
                    )
                }
            )

    _release_reservations(order)
    _, levels = _stock_map(order.quotation.company, demand.keys(), lock=True)

    warehouses_by_id = {}
    for entry in allocations:
        warehouses_by_id[entry["warehouse"].id] = entry["warehouse"]

    _reserve_plan(
        [
            (warehouses_by_id[warehouse_id], products_by_id[product_id], qty)
            for (product_id, warehouse_id), qty in requested.items()
        ],
        levels,
    )

    order.split_lines.all().delete()
    for (product_id, warehouse_id), qty in requested.items():
        if qty <= ZERO:
            continue
        warehouse = warehouses_by_id[warehouse_id]
        WarehouseSplitLine.objects.create(
            fulfillment_order=order,
            warehouse=warehouse,
            product=products_by_id[product_id],
            qty_fulfilled=_q2(qty),
            est_shipment_count=1,
            cost=_q2(Decimal(warehouse.shipping_cost_weight) * qty),
            is_override=True,
        )

    # Whatever the operator left unallocated is still owed to the customer — it becomes a
    # backorder line rather than quietly shrinking the order.
    cheapest = (
        Warehouse.objects.filter(company=order.quotation.company)
        .order_by("shipping_cost_weight", "id")
        .first()
    )
    for product_id, needed in demand_by_id.items():
        short = needed - per_product.get(product_id, ZERO)
        if short > ZERO:
            WarehouseSplitLine.objects.create(
                fulfillment_order=order,
                warehouse=cheapest,
                product=products_by_id[product_id],
                qty_fulfilled=_q2(short),
                est_shipment_count=0,
                cost=ZERO,
                is_backorder=True,
                is_override=True,
            )

    order.status = (
        FulfillmentOrder.BACKORDERED if order.has_backorder else FulfillmentOrder.ACCEPTED
    )
    order.promised_date = _promised_date(order.has_backorder)
    order.save(update_fields=["status", "promised_date", "updated_at"])
    _sync_backorder_event(order, actor, note="Raised by a manual override leaving qty unallocated.")

    record(
        order.quotation.company,
        actor,
        order.quotation,
        "fulfillment_split_overridden",
        reason=reason or "Manual warehouse split override.",
        fulfillment_order_id=str(order.id),
        shipment_count=order.shipment_count,
        has_backorder=order.has_backorder,
        allocations=[
            {
                "warehouse": warehouses_by_id[warehouse_id].name,
                "product": products_by_id[product_id].name,
                "qty": str(_q2(qty)),
            }
            for (product_id, warehouse_id), qty in requested.items()
        ],
    )
    return order


# --------------------------------------------------------------------------------------
# Replenishment watcher + consolidation (§7.2.6)
# --------------------------------------------------------------------------------------


def _own_unreserved_claim(backorder_line):
    """How much of this warehouse's free stock the same order is already relying on for
    its in-stock lines. Only meaningful before the split is accepted; once accepted those
    units have left `qty_available` for real."""
    total = WarehouseSplitLine.objects.filter(
        fulfillment_order_id=backorder_line.fulfillment_order_id,
        warehouse_id=backorder_line.warehouse_id,
        product_id=backorder_line.product_id,
        is_backorder=False,
    ).aggregate(total=models.Sum("qty_fulfilled"))["total"]
    return total or ZERO


def scan_backorder_replenishment(company=None):
    """Watch `stock_level` for replenishment and *flag* — never apply — consolidation.

    This is the body of the Celery Beat "backorder-consolidation watcher" (§14). Celery
    is not wired yet, so it is driven by `POST /api/fulfillment/scan-replenishment` and
    the `scan_backorder_replenishment` management command; moving it onto a beat schedule
    later needs no change here.

    Applying a consolidation reserves stock and changes what ships, so the scan only
    lights up the prompt. The `backorder_event` stays open until someone actually accepts
    the consolidation — an event marked resolved before anything shipped would be a lie
    to Deal Health further down the line.
    """
    lines = WarehouseSplitLine.objects.filter(
        is_backorder=True,
        fulfillment_order__backorder_events__resolved=False,
    ).select_related("warehouse", "product", "fulfillment_order")
    if company is not None:
        lines = lines.filter(fulfillment_order__quotation__company=company)

    flagged, cleared = [], []
    # Read straight from stock_level on every pass — the whole point of the watcher is to
    # notice a restock that happened outside this app entirely.
    for line in lines.distinct():
        level = StockLevel.objects.filter(
            warehouse_id=line.warehouse_id, product_id=line.product_id
        ).first()
        available = level.qty_available if level else ZERO

        if line.fulfillment_order.status not in FulfillmentOrder.RESERVED_STATUSES:
            # A split that has only been suggested holds no reservation, so the units it
            # already plans to ship from this warehouse are still sitting in
            # qty_available. Netting them off is what stops the order being told that the
            # very stock it is counting on is spare — without it a shortfall would flag
            # itself the moment it was created.
            own_claim = _own_unreserved_claim(line)
            available -= own_claim

        can_consolidate = line.qty_fulfilled > ZERO and available >= line.qty_fulfilled
        if can_consolidate != line.consolidation_available:
            line.consolidation_available = can_consolidate
            line.save(update_fields=["consolidation_available", "updated_at"])
            (flagged if can_consolidate else cleared).append(line)
    return {"flagged": flagged, "cleared": cleared}


@transaction.atomic
def consolidate_backorder(order, actor, line_ids=None):
    """Apply a flagged consolidation: turn backorder lines back into real allocations and
    reserve the replenished stock. Only lines the watcher has flagged are eligible, and
    the reservation goes through the same oversell check as everything else."""
    lines = order.split_lines.filter(is_backorder=True, consolidation_available=True)
    if line_ids:
        lines = lines.filter(id__in=line_ids)
    lines = list(lines.select_related("warehouse", "product"))
    if not lines:
        raise ValidationError(
            {"detail": "No backorder line on this order is ready to consolidate yet."}
        )

    # Consolidating a split that was never accepted has to take a hold on the whole thing,
    # not just the recovered units — otherwise the order lands in "accepted" while most of
    # its quantity is still unreserved and free for the next order to take.
    to_reserve = list(lines)
    if order.status not in FulfillmentOrder.RESERVED_STATUSES:
        to_reserve += list(
            order.split_lines.filter(is_backorder=False).select_related("warehouse", "product")
        )

    _, levels = _stock_map(
        order.quotation.company, {line.product for line in to_reserve}, lock=True
    )
    _reserve_plan(
        [(line.warehouse, line.product, line.qty_fulfilled) for line in to_reserve], levels
    )

    for line in lines:
        # If the order already ships this product from this warehouse, fold the recovered
        # units into that line — two rows for one (warehouse, product) would show up as a
        # second shipment and read as a half-empty allocation on the split table.
        existing = (
            order.split_lines.filter(
                warehouse_id=line.warehouse_id, product_id=line.product_id, is_backorder=False
            )
            .exclude(pk=line.pk)
            .first()
        )
        if existing:
            existing.qty_fulfilled += line.qty_fulfilled
            existing.cost = _q2(
                Decimal(line.warehouse.shipping_cost_weight) * existing.qty_fulfilled
            )
            existing.save(update_fields=["qty_fulfilled", "cost", "updated_at"])
            line.delete()
            continue

        line.is_backorder = False
        line.consolidation_available = False
        line.est_shipment_count = 1
        line.cost = _q2(Decimal(line.warehouse.shipping_cost_weight) * line.qty_fulfilled)
        line.save(
            update_fields=[
                "is_backorder",
                "consolidation_available",
                "est_shipment_count",
                "cost",
                "updated_at",
            ]
        )

    order.refresh_from_db()
    order.status = (
        FulfillmentOrder.BACKORDERED if order.has_backorder else FulfillmentOrder.ACCEPTED
    )
    order.promised_date = _promised_date(order.has_backorder)
    order.save(update_fields=["status", "promised_date", "updated_at"])

    consolidated = ", ".join(f"{line.product.name} x{_q2(line.qty_fulfilled)}" for line in lines)
    _sync_backorder_event(order, actor, note=f"Consolidated from replenished stock: {consolidated}.")

    record(
        order.quotation.company,
        actor,
        order.quotation,
        "fulfillment_backorder_consolidated",
        reason=f"Replenished stock allocated: {consolidated}.",
        fulfillment_order_id=str(order.id),
        has_backorder=order.has_backorder,
    )
    return order


def notify_backorder_customer(order, actor, note=""):
    """Records that the customer was told about the shortfall. The actual email lands with
    the portal/notification work in a later phase; the timestamp is what the banner and
    the audit trail need now."""
    event = order.open_backorder_event
    if event is None:
        raise ValidationError({"detail": "This order has no open backorder."})
    event.customer_notified_at = timezone.now()
    if note:
        event.resolution_note = note
    event.save(update_fields=["customer_notified_at", "resolution_note"])

    record(
        order.quotation.company,
        actor,
        order.quotation,
        "backorder_customer_notified",
        reason=note or "Customer notified of the backordered quantity.",
        fulfillment_order_id=str(order.id),
        backorder_event_id=str(event.id),
    )
    return event
