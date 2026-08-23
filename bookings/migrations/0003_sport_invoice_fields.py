from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bookings", "0002_callsession"),
    ]

    operations = [
        migrations.AddField(
            model_name="sport",
            name="legal_name",
            field=models.CharField(blank=True, max_length=160),
        ),
        migrations.AddField(
            model_name="sport",
            name="address",
            field=models.TextField(blank=True),
        ),
        migrations.AddField(
            model_name="sport",
            name="gstin",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="sport",
            name="upi_vpa",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="sport",
            name="invoice_prefix",
            field=models.CharField(blank=True, max_length=8),
        ),
    ]
