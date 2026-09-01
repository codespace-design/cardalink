from django.db import migrations

def create_default_admin(apps, schema_editor):
    User = apps.get_model("users", "User")
    if not User.objects.filter(email="admin@cardalink.com").exists():
        from django.contrib.auth.hashers import make_password
        admin_user = User(
            email="admin@cardalink.com",
            name="CardaLink Admin",
            role="ADMIN",
            status="ACTIVE",
            is_staff=True,
            is_superuser=True,
            is_active=True
        )
        admin_user.password = make_password("AdminPassword123")
        admin_user.save()

def remove_default_admin(apps, schema_editor):
    User = apps.get_model("users", "User")
    User.objects.filter(email="admin@cardalink.com").delete()

class Migration(migrations.Migration):
    dependencies = [
        ("users", "0003_remove_user_area_unit_remove_user_business_address_and_more"),
    ]

    operations = [
        migrations.RunPython(create_default_admin, remove_default_admin),
    ]
