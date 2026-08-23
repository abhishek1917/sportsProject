from django.test import TestCase

from billing.services import rupees_to_paise


class BillingHelpersTests(TestCase):
    def test_rupees_to_paise(self):
        self.assertEqual(rupees_to_paise("4500"), 450000)
        self.assertEqual(rupees_to_paise("0"), 0)
