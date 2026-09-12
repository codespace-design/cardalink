import functools
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied


def is_admin_user(view_func):
    """Decorator for views that checks that the user is authenticated and has role 'ADMIN'."""
    @functools.wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        if request.user.role != "ADMIN" and not request.user.is_superuser:
            raise PermissionDenied("Only administrators can access this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped_view


class AdminRequiredMixin(AccessMixin):
    """CBV Mixin to verify that the current user is authenticated and an administrator."""

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied("Authentication required.")
        if request.user.role != "ADMIN" and not request.user.is_superuser:
            raise PermissionDenied("Only administrators can access this page.")
        return super().dispatch(request, *args, **kwargs)
