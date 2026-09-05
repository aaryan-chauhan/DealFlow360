from .models import Membership

COMPANY_HEADER = "HTTP_X_COMPANY_ID"


def resolve_active_membership(user, company_id=None):
    """The membership every RBAC + tenant-scoping check keys off (spec §3, §12)."""
    if not user or not user.is_authenticated:
        return None
    qs = Membership.objects.select_related("company", "role").filter(user=user)
    if company_id:
        return qs.filter(company_id=company_id).first()
    return qs.filter(is_active_default=True).first() or qs.first()


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
