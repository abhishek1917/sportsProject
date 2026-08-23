from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from attendance.models import CoachAssignment, FacilityManager, StaffVenue, Student
from bookings.models import Sport

User = get_user_model()


class Command(BaseCommand):
    help = "Create a facility owner, manager, or coach login."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument("password")
        parser.add_argument("--sport", default="tennis", help="Primary sport slug")
        parser.add_argument(
            "--role",
            choices=[
                FacilityManager.ROLE_OWNER,
                FacilityManager.ROLE_MANAGER,
                FacilityManager.ROLE_COACH,
            ],
            default=FacilityManager.ROLE_OWNER,
        )
        parser.add_argument("--name", default="", help="Display name")
        parser.add_argument(
            "--venues",
            default="",
            help="Comma-separated extra sport slugs for owners (e.g. tennis,cricket)",
        )
        parser.add_argument(
            "--session",
            default="",
            help="Batch for coaches: morning, evening, or night",
        )

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
        StaffVenue.objects.update_or_create(
            staff=manager, sport=sport, defaults={"is_default": True}
        )
        extra = [slug.strip() for slug in options["venues"].split(",") if slug.strip()]
        for slug in extra:
            extra_sport = Sport.objects.filter(slug=slug).first()
            if extra_sport:
                StaffVenue.objects.get_or_create(staff=manager, sport=extra_sport)
        session = options["session"]
        if manager.role == FacilityManager.ROLE_COACH and session in {
            Student.SESSION_MORNING,
            Student.SESSION_EVENING,
            Student.SESSION_NIGHT,
        }:
            CoachAssignment.objects.get_or_create(
                staff=manager, sport=sport, session=session, court_label=""
            )
        verb = "Created" if created or mgr_created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} {manager.get_role_display().lower()} '{user.username}' for {sport.name}."
            )
        )
