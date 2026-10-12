from django.core.management.base import BaseCommand
from apps.accounts.models import User
from apps.patients.models import Department

class Command(BaseCommand):
    help = "Creates local development departments and demo accounts. Never use demo passwords in production."
    def handle(self, *args, **options):
        for name, code in [("Outpatient Department", "opd"), ("Emergency", "emergency"), ("Maternity", "maternity"), ("Pediatrics", "pediatrics")]:
            Department.objects.get_or_create(code=code, defaults={"name": name})
        for username, password, role, display_name in [("admin", "admin123", "admin", "Administrator"), ("manager", "manager123", "admin", "Operations Admin"), ("doctor", "doctor123", "doctor", "Dr. Demo"), ("nurse", "nurse123", "nurse", "Nurse Demo")]:
            user, created = User.objects.get_or_create(username=username, defaults={"role": role, "display_name": display_name, "is_staff": role == "admin"})
            if created: user.set_password(password); user.save()
        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
