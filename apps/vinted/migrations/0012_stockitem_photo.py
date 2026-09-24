from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("vinted", "0011_saleorderline"),
    ]

    operations = [
        migrations.AddField(
            model_name="stockitem",
            name="photo",
            field=models.URLField(blank=True, help_text="URL thumbnail de la carte (Pokellector, scan perso…)"),
        ),
    ]
