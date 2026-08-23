from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User

from bookings.models import Customer


class FlexibleAuthBackend(ModelBackend):
    """Allow login with username, email, or phone number."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not username or password is None:
            return None
        user = self._find_user(username.strip())
        if user is None:
            return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None

    def _find_user(self, raw: str) -> User | None:
        user = User.objects.filter(username__iexact=raw).first()
        if user:
            return user
        if "@" in raw:
            user = User.objects.filter(email__iexact=raw).first()
            if user:
                return user
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) >= 10:
            tail = digits[-10:]
            customer = (
                Customer.objects.filter(phone__endswith=tail)
                .select_related("user")
                .first()
            )
            if customer:
                return customer.user
        return None
