from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from attendance.models import FacilityManager
from bookings.models import Sport

User = get_user_model()


class Command(BaseCommand):
    help = "Create a facility owner or manager login scoped to one sport."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")
        parser.add_argument("--sport", default="tennis", help="Sport slug, e.g. tennis")
        parser.add_argument(
            "--role",
            choices=[FacilityManager.ROLE_OWNER, FacilityManager.ROLE_MANAGER],
            default=FacilityManager.ROLE_OWNER,
        )
        parser.add_argument("--name", default="", help="Display name")

    def handle(self, *args, **options):
        sport = Sport.objects.filter(slug=options["sport"]).first()
        if sport is None:
            raise CommandError(
                f"Sport '{options['sport']}' not found. Run: python manage.py seed_sports"
            )
        user, created = User.objects.get_or_create(username=options["username"])
        user.set_password(options["password"])
        if options["name"]:
            user.first_name = options["name"][:30]
        user.save()
        manager, mgr_created = FacilityManager.objects.update_or_create(
            user=user,
            defaults={
                "sport": sport,
                "role": options["role"],
                "display_name": options["name"] or user.get_full_name(),
            },
        )
        verb = "Created" if created or mgr_created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {manager.get_role_display().lower()} '{user.username}' for {sport.name}."
            )
        )
