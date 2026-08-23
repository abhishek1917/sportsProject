from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponseForbidden
from django.urls import reverse


def manager_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(), login_url=reverse("attendance:login")
            )
        manager = getattr(request.user, "facility_manager", None)
        if manager is None:
            return HttpResponseForbidden(
                "Only facility owners and managers can open this panel."
            )
        request.facility_manager = manager
        request.managed_sport = manager.sport
        return view_func(request, *args, **kwargs)

    return _wrapped
