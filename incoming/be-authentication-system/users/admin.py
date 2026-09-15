from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import StaffProfile, StudentProfile, User


class StudentProfileInline(admin.StackedInline):
    model = StudentProfile
    can_delete = False
    verbose_name_plural = 'Student Profile'
    fk_name = 'user'
    extra = 0
    readonly_fields = ('health_card_no', 'created_at', 'updated_at')


class StaffProfileInline(admin.StackedInline):
    model = StaffProfile
    can_delete = False
    verbose_name_plural = 'Staff Profile'
    fk_name = 'user'
    extra = 0
    readonly_fields = ('created_at', 'updated_at')


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = (StudentProfileInline, StaffProfileInline)
    list_display = ('unique_id', 'name', 'email', 'role', 'is_staff', 'is_active', 'created_at')
    list_filter = ('role', 'is_staff', 'is_active')
    fieldsets = (
        (None, {'fields': ('unique_id', 'password')}),
        ('Personal Info', {'fields': ('name', 'email', 'role')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'created_at', 'updated_at')}),
    )
    readonly_fields = ('created_at', 'updated_at', 'last_login')
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('unique_id', 'name', 'email', 'role', 'password', 'is_active', 'is_staff', 'is_superuser'),
        }),
    )
    search_fields = ('unique_id', 'name', 'email')
    ordering = ('unique_id',)


@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ('health_card_no', 'user', 'department', 'level', 'phone', 'dob', 'created_at')
    search_fields = ('health_card_no', 'user__unique_id', 'user__name', 'user__email', 'phone', 'department')
    list_filter = ('level', 'gender', 'department')
    readonly_fields = ('health_card_no', 'created_at', 'updated_at')


@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'department', 'gender', 'phone_number', 'created_at')
    search_fields = ('name', 'user__unique_id', 'user__email', 'phone_number', 'department')
    list_filter = ('gender', 'department')
    readonly_fields = ('created_at', 'updated_at')
