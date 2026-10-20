from django.contrib import admin

from .models import Holiday, QueueSettings, ServiceHours, StaffShift

admin.site.register([Holiday, QueueSettings, ServiceHours, StaffShift])
