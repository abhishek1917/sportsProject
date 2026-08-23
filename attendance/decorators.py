from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.urls import reverse

from .access import resolve_managed_sport


def staff_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(), login_url=reverse("attendance:login")
            )
        manager = getattr(request.user, "facility_manager", None)
        if manager is None:
            return HttpResponseForbidden(
                "Only facility owners, managers, and coaches can open this panel."
            )
        request.facility_manager = manager
        request.managed_sport = resolve_managed_sport(request, manager)
        return view_func(request, *args, **kwargs)

    return _wrapped


def manager_required(view_func):
    @staff_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if request.facility_manager.is_coach():
            return HttpResponseForbidden("Coaches cannot open this page.")
        return view_func(request, *args, **kwargs)

    return _wrapped
