from __future__ import annotations

import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from stadium_booking.deploy_keys import production_key


class Command(BaseCommand):
    help = "Create the default admin user on Render when env vars are not set."

    def handle(self, *args, **options):
        if not os.getenv("RENDER"):
            return

        username = (
            os.getenv("DJANGO_SUPERUSER_USERNAME", "").strip()
            or production_key("DJANGO_SUPERUSER_USERNAME")
        )
        password = (
            os.getenv("DJANGO_SUPERUSER_PASSWORD", "").strip()
            or production_key("DJANGO_SUPERUSER_PASSWORD")
        )
        email = (
            os.getenv("DJANGO_SUPERUSER_EMAIL", "").strip()
            or production_key("DJANGO_SUPERUSER_EMAIL")
        )
        if not username or not password:
            return

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user is None:
            User.objects.create_superuser(
                username=username,
                email=email or f"{username}@example.com",
                password=password,
            )
            self.stdout.write(self.style.SUCCESS(f"Created admin user '{username}'."))
            return

        if not user.is_superuser or not user.is_staff:
            user.is_superuser = True
            user.is_staff = True
            user.save(update_fields=["is_superuser", "is_staff"])
            self.stdout.write(self.style.SUCCESS(f"Promoted '{username}' to admin."))

        user.set_password(password)
        user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS(f"Admin password synced for '{username}'."))
