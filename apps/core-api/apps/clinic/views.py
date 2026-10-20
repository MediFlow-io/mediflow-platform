"""Clinic settings API. Everyone signed in may read (students see hours and holidays when booking);
only admins change anything, and every change is audited."""
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import STAFF_ROLES, IsAdmin, has_role
from apps.operations.audit import record
from apps.patients.models import Department

from .models import WEEKDAYS, Holiday, QueueSettings, ServiceHours, StaffShift


class AdminWriteOrSignedIn(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return IsAdmin().has_permission(request, view)


class QueueSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = QueueSettings
        exclude = ("id",)
        read_only_fields = ("updated_at",)

    def validate(self, data):
        for field in ("slot_minutes", "max_days_ahead"):
            if field in data and data[field] < 1:
                raise serializers.ValidationError({field: "Must be at least 1."})
        if "slot_minutes" in data and 1440 % data["slot_minutes"]:
            raise serializers.ValidationError({"slot_minutes": "Must divide a day evenly (e.g. 10, 15, 20, 30)."})
        return data


class HoursSerializer(serializers.ModelSerializer):
    day = serializers.SerializerMethodField()

    class Meta:
        model = ServiceHours
        fields = ("department", "weekday", "day", "opens", "closes")

    def get_day(self, obj):
        return WEEKDAYS[obj.weekday]


class DayHoursSerializer(serializers.Serializer):
    weekday = serializers.IntegerField(min_value=0, max_value=6)
    opens = serializers.TimeField()
    closes = serializers.TimeField()

    def validate(self, data):
        if data["closes"] <= data["opens"]:
            raise serializers.ValidationError({"closes": "Closing time must be after opening time."})
        return data


class HoursUpdateSerializer(serializers.Serializer):
    """Replaces the whole week for one department (or the clinic default when department is null).
    An empty list removes the department's own hours, so it falls back to the default."""
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all(), allow_null=True)
    days = DayHoursSerializer(many=True)

    def validate_days(self, days):
        weekdays = [d["weekday"] for d in days]
        if len(weekdays) != len(set(weekdays)):
            raise serializers.ValidationError("Each weekday may appear once.")
        return days


class HolidaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Holiday
        fields = ("id", "date", "name")


class ShiftSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source="user.display_name", read_only=True)
    role = serializers.CharField(source="user.role", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    day = serializers.SerializerMethodField()

    class Meta:
        model = StaffShift
        fields = ("id", "user", "user_name", "role", "department", "department_name", "weekday", "day", "starts", "ends")

    def get_day(self, obj):
        return WEEKDAYS[obj.weekday]

    def validate_user(self, user):
        if not user.is_active or user.role not in STAFF_ROLES:
            raise serializers.ValidationError("Choose an active staff member.")
        return user

    def validate(self, data):
        if data["ends"] <= data["starts"]:
            raise serializers.ValidationError({"ends": "The shift must end after it starts."})
        return data


class ClinicSettingsView(APIView):
    """GET /api/clinic/settings: everything a client needs in one call."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()
        data = {
            "queue": QueueSettingsSerializer(QueueSettings.load()).data,
            "hours": HoursSerializer(ServiceHours.objects.all(), many=True).data,
            "holidays": HolidaySerializer(Holiday.objects.filter(date__gte=today), many=True).data,
        }
        if has_role(request.user, STAFF_ROLES):
            data["onDutyNow"] = on_duty_now()
        return Response(data)


class QueueSettingsView(APIView):
    permission_classes = [AdminWriteOrSignedIn]

    def get(self, request):
        return Response(QueueSettingsSerializer(QueueSettings.load()).data)

    def put(self, request):
        current = QueueSettings.load()
        serializer = QueueSettingsSerializer(current, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        record(request.user, "settings.queue_updated", "queue_settings", 1, fields=sorted(serializer.validated_data))
        return Response(serializer.data)

    patch = put


class HoursView(APIView):
    permission_classes = [AdminWriteOrSignedIn]

    def get(self, request):
        return Response(HoursSerializer(ServiceHours.objects.all(), many=True).data)

    def put(self, request):
        serializer = HoursUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        department, days = serializer.validated_data["department"], serializer.validated_data["days"]
        with transaction.atomic():
            ServiceHours.objects.filter(department=department).delete()
            ServiceHours.objects.bulk_create(ServiceHours(department=department, **day) for day in days)
        record(request.user, "settings.hours_updated", "department" if department else "clinic",
               department.pk if department else "", days=len(days))
        return Response(HoursSerializer(ServiceHours.objects.filter(department=department), many=True).data)


class HolidayListView(generics.ListCreateAPIView):
    permission_classes = [AdminWriteOrSignedIn]
    serializer_class = HolidaySerializer

    def get_queryset(self):
        holidays = Holiday.objects.all()
        if self.request.query_params.get("upcoming") in ("1", "true"):
            holidays = holidays.filter(date__gte=timezone.localdate())
        return holidays

    def perform_create(self, serializer):
        holiday = serializer.save()
        record(self.request.user, "settings.holiday_added", "holiday", holiday.pk, date=str(holiday.date))


class HolidayDetailView(generics.RetrieveDestroyAPIView):
    permission_classes = [AdminWriteOrSignedIn]
    serializer_class = HolidaySerializer
    queryset = Holiday.objects.all()

    def perform_destroy(self, instance):
        record(self.request.user, "settings.holiday_removed", "holiday", instance.pk, date=str(instance.date))
        instance.delete()


class StaffOnly(AdminWriteOrSignedIn):
    def has_permission(self, request, view):
        return has_role(request.user, STAFF_ROLES) and super().has_permission(request, view)


class ShiftListView(generics.ListCreateAPIView):
    permission_classes = [StaffOnly]
    serializer_class = ShiftSerializer

    def get_queryset(self):
        shifts = StaffShift.objects.select_related("user", "department")
        params = self.request.query_params
        if params.get("department"):
            shifts = shifts.filter(department_id=params["department"])
        if params.get("user"):
            shifts = shifts.filter(user_id=params["user"])
        if params.get("weekday"):
            shifts = shifts.filter(weekday=params["weekday"])
        return shifts

    def perform_create(self, serializer):
        shift = serializer.save()
        record(self.request.user, "settings.shift_added", "shift", shift.pk, user=shift.user_id, weekday=shift.weekday)


class ShiftDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [StaffOnly]
    serializer_class = ShiftSerializer
    queryset = StaffShift.objects.select_related("user", "department")

    def perform_update(self, serializer):
        shift = serializer.save()
        record(self.request.user, "settings.shift_updated", "shift", shift.pk, fields=sorted(serializer.validated_data))

    def perform_destroy(self, instance):
        record(self.request.user, "settings.shift_removed", "shift", instance.pk)
        instance.delete()


def on_duty_now() -> dict:
    """Staff on shift right now, counted by role (feeds "doctors available" on dashboards)."""
    now = timezone.localtime()
    weekday = (now.weekday() + 1) % 7  # Python: Monday = 0; ours: Sunday = 0
    shifts = (StaffShift.objects.filter(weekday=weekday, starts__lte=now.time(), ends__gt=now.time(), user__is_active=True)
              .order_by().values_list("user__role", "user_id").distinct())
    counts: dict[str, int] = {}
    for role, _ in shifts:
        counts[role] = counts.get(role, 0) + 1
    return counts

