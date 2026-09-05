from .models import Membership, Role

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


def resolve_active_membership(user, company_id=None):
    """The membership every RBAC + tenant-scoping check keys off (spec §3, §12)."""
    if not user or not user.is_authenticated:
        return None
    qs = Membership.objects.select_related("company", "role").filter(user=user)
    if company_id:
        return qs.filter(company_id=company_id).first()
    return qs.filter(is_active_default=True).first() or qs.first()


def scope_to_owner(queryset, membership, user, owner_field="owner"):
    """Apply §12's owner rule in one place: a Sales Rep sees only their own records;
    every other role (Manager, Finance / Ops, Admin) sees the whole company.

    Quotations, Approvals and Fulfillment all need this rule, and all three used to spell
    it out themselves. Keeping one copy means a role can never be accidentally
    owner-filtered in one screen and not another — the failure mode here is a Finance user
    silently seeing a subset of the company's work and believing it is everything.
    """
    if membership is None:
        return queryset.none()
    if membership.role.code == Role.SALES_REP:
        return queryset.filter(**{owner_field: user})
    return queryset


def get_membership(request):
    """Resolved on first use and cached on the request; the acting company can be
    switched per-request with the `X-Company-Id` header (company/team selector)."""
    membership = getattr(request, "_active_membership", None)
    if membership is None:
        membership = resolve_active_membership(
            getattr(request, "user", None), request.META.get(COMPANY_HEADER) or None
        )
        request._active_membership = membership
    return membership
