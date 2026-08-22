from django.core.management.base import BaseCommand

from bookings.calls import CallError, configure_twilio_inbound_webhook


class Command(BaseCommand):
    help = "Point your Twilio number's voice webhook at /voice/inbound/ on this server."

    def handle(self, *args, **options):
        try:
            url = configure_twilio_inbound_webhook()
        except CallError as exc:
            self.stderr.write(self.style.ERROR(str(exc)))
            return
        self.stdout.write(self.style.SUCCESS(f"Twilio voice webhook set to {url}"))
