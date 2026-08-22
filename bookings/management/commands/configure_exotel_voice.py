from django.conf import settings
from django.core.management.base import BaseCommand

from bookings.calls import exotel_inbound_webhook_url, fetch_exotel_exophone


class Command(BaseCommand):
    help = "Show Exotel App Bazaar setup for Book on Call."

    def handle(self, *args, **options):
        if not settings.EXOTEL_ACCOUNT_SID:
            self.stderr.write(self.style.ERROR("EXOTEL_ACCOUNT_SID is missing in .env"))
            return
        if not settings.EXOTEL_API_KEY or not settings.EXOTEL_API_TOKEN:
            self.stderr.write(self.style.ERROR("EXOTEL_API_KEY / EXOTEL_API_TOKEN missing in .env"))
            return
        if not settings.PUBLIC_BASE_URL:
            self.stderr.write(self.style.ERROR("PUBLIC_BASE_URL is missing in .env"))
            return

        webhook = exotel_inbound_webhook_url()
        self.stdout.write(self.style.SUCCESS("Exotel Book on Call setup"))
        self.stdout.write(f"Account SID: {settings.EXOTEL_ACCOUNT_SID}")
        self.stdout.write(f"Webhook URL: {webhook}")
        self.stdout.write("")
        self.stdout.write("In Exotel dashboard:")
        self.stdout.write("1. App Bazaar -> create/open your incoming call flow")
        self.stdout.write("2. Set ExoPhone voice URL to the webhook above (GET or POST)")
        self.stdout.write("   OR use Passthru/URL applet pointing to that webhook")
        self.stdout.write("3. Exotel should receive ExoML (Say + Record) from your server")

        try:
            number = fetch_exotel_exophone()
        except Exception as exc:
            self.stderr.write(self.style.WARNING(f"Could not fetch ExoPhone automatically: {exc}"))
            return
        if number:
            self.stdout.write(self.style.SUCCESS(f"ExoPhone on account: {number}"))
            self.stdout.write("Set EXOTEL_FROM_NUMBER in .env if not already set.")
