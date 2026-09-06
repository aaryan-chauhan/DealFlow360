"""DRF permission classes for the roles defined in spec §3.

Phase 1 ships the role/company gate; object-level rules that need tables from later
phases (approval steps, portal sessions) are marked below and land with those apps.
"""

from rest_framework.permissions import SAFE_METHODS, BasePermission

from .models import Role
from .scoping import get_membership


class HasRole(BasePermission):
    required_roles = ()

    def has_permission(self, request, view):
        membership = get_membership(request)
        if membership is None:
            return False
        return membership.role.code in self.required_roles


class IsSalesRep(HasRole):
    required_roles = (Role.SALES_REP, Role.SALES_MANAGER, Role.ADMIN)


class IsSalesManager(HasRole):
    required_roles = (Role.SALES_MANAGER, Role.ADMIN)


class IsFinance(HasRole):
    required_roles = (Role.FINANCE_OPS, Role.ADMIN)


class IsAdmin(HasRole):
    required_roles = (Role.ADMIN,)


class IsCompanyMember(BasePermission):
    """Any authenticated user with a membership in the acting company."""

    def has_permission(self, request, view):
        return get_membership(request) is not None


class MemberReadRoleWrite(BasePermission):
    """Any member of the acting company may read; only `write_roles` may change config."""

    write_roles = ()

    def has_permission(self, request, view):
        membership = get_membership(request)
        if membership is None:
            return False
        if request.method in SAFE_METHODS:
            return True
        return membership.role.code in self.write_roles


class IsAdminOrReadOnly(MemberReadRoleWrite):
    """Catalog + price lists — Admin-only configuration (§9 screens 16-17)."""

    write_roles = (Role.ADMIN,)


class CanConfigureDiscounts(MemberReadRoleWrite):
    """Discount tiers, category ceilings, approval chains — Admin, and Manager per §3."""

    write_roles = (Role.ADMIN, Role.SALES_MANAGER)


STAGE_ROLES = {
    "manager": (Role.SALES_MANAGER, Role.ADMIN),
    "finance": (Role.FINANCE_OPS, Role.ADMIN),
}


def IsApproverForStage(stage):
    """Role gate for an approval stage. The `approvals` app (phase 3) extends this with
    the object-level check that the acting user matches the *current pending step*."""

    class _IsApproverForStage(HasRole):
        required_roles = STAGE_ROLES[stage]

    _IsApproverForStage.__name__ = f"IsApproverFor{stage.title()}"
    return _IsApproverForStage
