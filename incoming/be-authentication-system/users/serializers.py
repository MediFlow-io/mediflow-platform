import re
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from .models import GenderChoices, RoleChoices, StaffProfile, StudentProfile, User

# Regex for Matric No format (e.g. SEN/22/9269 or CSC/2021/1002)
MATRIC_REGEX = re.compile(r'^[A-Za-z]{2,6}/\d{2,4}/\d{3,6}$')

# Regex for 11 digits phone number (e.g. 08012345678)
PHONE_REGEX = re.compile(r'^\d{11}$')

# Valid staff roles (all roles except Student)
STAFF_ROLES = [
    RoleChoices.ADMIN,
    RoleChoices.DOCTOR,
    RoleChoices.NURSE,
    RoleChoices.RECEPTION,
    RoleChoices.LAB,
    RoleChoices.PHARMACY,
    RoleChoices.IT,
]


class StudentRegistrationSerializer(serializers.Serializer):
    """
    Serializer for registering a new student patient in the MediFlow system.
    Validates matric format, phone length, age >= 16, and password strength.
    """
    name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Full legal name of the student"
    )
    unique_id = serializers.CharField(
        max_length=50,
        required=True,
        help_text="Student Matriculation Number (e.g. SEN/22/9269)"
    )
    email = serializers.EmailField(
        required=True,
        help_text="Valid, unique email address"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Secure password (minimum 8 characters, checked against standard validators)"
    )
    gender = serializers.ChoiceField(
        choices=GenderChoices.choices,
        required=True,
        help_text="Gender choice: Male, Female, or Other"
    )
    dob = serializers.DateField(
        required=True,
        help_text="Date of birth in YYYY-MM-DD format (must be >= 16 years old)"
    )
    address = serializers.CharField(
        required=True,
        help_text="Residential or campus address"
    )
    department = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Academic department (e.g. Software Engineering)"
    )
    level = serializers.CharField(
        max_length=20,
        required=True,
        help_text="Academic level (e.g. 100, 200, 300, 400, 500)"
    )
    phone = serializers.CharField(
        max_length=11,
        required=True,
        help_text="11-digit phone number (e.g. 08012345678)"
    )

    def validate_unique_id(self, value):
        cleaned_value = value.strip().upper()
        if not MATRIC_REGEX.match(cleaned_value):
            raise serializers.ValidationError(
                "Invalid Matric Number format. Expected format like 'SEN/22/9269'."
            )
        if User.objects.filter(unique_id__iexact=cleaned_value).exists():
            raise serializers.ValidationError(
                "A user with this Matriculation Number already exists."
            )
        return cleaned_value

    def validate_email(self, value):
        cleaned_email = value.strip().lower()
        if User.objects.filter(email__iexact=cleaned_email).exists():
            raise serializers.ValidationError(
                "A user with this email address already exists."
            )
        return cleaned_email

    def validate_phone(self, value):
        cleaned_phone = value.strip()
        if not PHONE_REGEX.fullmatch(cleaned_phone):
            raise serializers.ValidationError(
                "Phone number must be exactly 11 digits (e.g. 08012345678)."
            )
        return cleaned_phone

    def validate_dob(self, value):
        today = timezone.now().date()
        if value > today:
            raise serializers.ValidationError("Date of birth cannot be in the future.")

        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 16:
            raise serializers.ValidationError(
                f"Student must be at least 16 years old. Current age is {age} years."
            )
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        with transaction.atomic():
            user = User.objects.create_user(
                unique_id=validated_data['unique_id'],
                email=validated_data['email'],
                password=validated_data['password'],
                name=validated_data['name'],
                role=RoleChoices.STUDENT
            )

            health_card_no = StudentProfile.generate_next_health_card_no()

            StudentProfile.objects.create(
                user=user,
                gender=validated_data['gender'],
                dob=validated_data['dob'],
                address=validated_data['address'],
                department=validated_data['department'],
                level=validated_data['level'],
                phone=validated_data['phone'],
                health_card_no=health_card_no
            )

            return user


class StudentRegistrationResponseSerializer(serializers.Serializer):
    """
    Response schema returned upon successful student registration.
    """
    id = serializers.IntegerField(help_text="User ID")
    name = serializers.CharField(help_text="Full Name")
    unique_id = serializers.CharField(help_text="Matriculation Number")
    email = serializers.EmailField(help_text="Email Address")
    role = serializers.CharField(help_text="Assigned Role (Student)")
    health_card_no = serializers.CharField(
        source='student_profile.health_card_no',
        help_text="Auto-generated Health Card Number (<number>/<registration_year>)"
    )
    gender = serializers.CharField(source='student_profile.gender')
    dob = serializers.DateField(source='student_profile.dob')
    department = serializers.CharField(source='student_profile.department')
    level = serializers.CharField(source='student_profile.level')
    phone = serializers.CharField(source='student_profile.phone')
    address = serializers.CharField(source='student_profile.address')
    created_at = serializers.DateTimeField()


class StaffRegistrationSerializer(serializers.Serializer):
    """
    Serializer for registering hospital staff members (Doctor, Nurse, Admin, Reception, etc.).
    Restricted to non-Student roles and validates staff profile fields.
    """
    unique_id = serializers.CharField(
        max_length=64,
        required=True,
        help_text="Staff ID (e.g. 2018002, DOC/001, or STF-102)"
    )
    email = serializers.EmailField(
        required=True,
        help_text="Official email address of the staff member"
    )
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'},
        help_text="Secure password (minimum 8 characters)"
    )
    role = serializers.ChoiceField(
        choices=[choice for choice in RoleChoices.choices if choice[0] != RoleChoices.STUDENT],
        required=True,
        help_text="Staff role: Admin, Doctor, Nurse, Reception, Lab, Pharmacy, IT"
    )
    name = serializers.CharField(
        max_length=255,
        required=True,
        help_text="Full legal name of the staff member"
    )
    gender = serializers.ChoiceField(
        choices=GenderChoices.choices,
        required=True,
        help_text="Gender choice: Male, Female, or Other"
    )
    department = serializers.CharField(
        max_length=100,
        required=True,
        help_text="Hospital department (e.g. Cardiology, IT, General Practice)"
    )
    phone_number = serializers.CharField(
        max_length=11,
        required=True,
        help_text="11-digit phone number (e.g. 08012345678)"
    )

    def validate_unique_id(self, value):
        cleaned_id = value.strip()
        if User.objects.filter(unique_id__iexact=cleaned_id).exists():
            raise serializers.ValidationError(
                "A user with this Staff ID already exists."
            )
        return cleaned_id

    def validate_email(self, value):
        cleaned_email = value.strip().lower()
        if User.objects.filter(email__iexact=cleaned_email).exists():
            raise serializers.ValidationError(
                "A user with this email address already exists."
            )
        return cleaned_email

    def validate_role(self, value):
        if value == RoleChoices.STUDENT:
            raise serializers.ValidationError(
                "Staff registration cannot be used to register a Student."
            )
        if value not in [choice[0] for choice in RoleChoices.choices if choice[0] != RoleChoices.STUDENT]:
            raise serializers.ValidationError(
                "Invalid staff role. Must be one of: Admin, Doctor, Nurse, Reception, Lab, Pharmacy, IT."
            )
        return value

    def validate_phone_number(self, value):
        cleaned_phone = value.strip()
        if not PHONE_REGEX.fullmatch(cleaned_phone):
            raise serializers.ValidationError(
                "Phone number must be exactly 11 digits (e.g. 08012345678)."
            )
        return cleaned_phone

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages))
        return value

    def create(self, validated_data):
        with transaction.atomic():
            is_staff = validated_data['role'] == RoleChoices.ADMIN
            user = User.objects.create_user(
                unique_id=validated_data['unique_id'],
                email=validated_data['email'],
                password=validated_data['password'],
                name=validated_data['name'],
                role=validated_data['role'],
                is_staff=is_staff
            )

            StaffProfile.objects.create(
                user=user,
                name=validated_data['name'],
                gender=validated_data['gender'],
                department=validated_data['department'],
                phone_number=validated_data['phone_number']
            )

            return user


class StaffProfileResponseSerializer(serializers.ModelSerializer):
    """
    Nested serializer representing the staff profile details.
    """
    class Meta:
        model = StaffProfile
        fields = ['name', 'gender', 'department', 'phone_number']


class StaffRegistrationResponseSerializer(serializers.Serializer):
    """
    Response schema returned upon successful staff registration.
    """
    message = serializers.CharField(
        default="Staff member registered successfully.",
        help_text="Confirmation message"
    )
    unique_id = serializers.CharField(help_text="Staff ID")
    role = serializers.CharField(help_text="Assigned staff role")
    email = serializers.EmailField(help_text="Staff email address")
    profile = StaffProfileResponseSerializer(
        source='staff_profile',
        help_text="Staff profile details"
    )


class LoginRequestSerializer(serializers.Serializer):
    """
    Credentials required to authenticate a user.
    """
    unique_id = serializers.CharField(
        required=True,
        help_text="Matric No (for Students) or Staff ID (for Personnel), e.g. SEN/22/9269 or 2018002"
    )
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Account password"
    )


class LoginResponseSerializer(serializers.Serializer):
    """
    Authentication payload containing JWT tokens and user metadata.
    """
    access = serializers.CharField(help_text="JWT Access Token (Bearer)")
    refresh = serializers.CharField(help_text="JWT Refresh Token")
    role = serializers.CharField(help_text="User role (Admin, Doctor, Nurse, Student, etc.)")
    id = serializers.IntegerField(help_text="Unique User ID")
    unique_id = serializers.CharField(help_text="Matric No or Staff ID")
    name = serializers.CharField(help_text="Full Name of the authenticated user")
    email = serializers.EmailField(help_text="User's email address")


class LogoutRequestSerializer(serializers.Serializer):
    """
    Request payload containing the refresh token to be blacklisted.
    """
    refresh = serializers.CharField(
        required=True,
        help_text="The JWT refresh token to be revoked/blacklisted."
    )


class LogoutResponseSerializer(serializers.Serializer):
    """
    Response returned upon successful token revocation.
    """
    detail = serializers.CharField(
        default="Successfully logged out.",
        help_text="Status message confirming token revocation"
    )


class ChangePasswordRequestSerializer(serializers.Serializer):
    """
    Payload for changing the authenticated user's password.
    """
    old_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Current password"
    )
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="New password (must comply with strength requirements)"
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'},
        help_text="Confirmation of new password"
    )

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Current password is incorrect.")
        return value

    def validate(self, attrs):
        old_password = attrs.get('old_password')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        if new_password != confirm_password:
            raise serializers.ValidationError({
                "confirm_password": "The new password and confirm password fields do not match."
            })

        if old_password == new_password:
            raise serializers.ValidationError({
                "new_password": "The new password cannot be the same as the current password."
            })

        user = self.context['request'].user
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)})

        return attrs


class ChangePasswordResponseSerializer(serializers.Serializer):
    """
    Response message for successful password change.
    """
    detail = serializers.CharField(
        default="Password changed successfully.",
        help_text="Confirmation message"
    )


class MessageResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Descriptive response message")


class ErrorResponseSerializer(serializers.Serializer):
    detail = serializers.CharField(help_text="Error message explaining failure reason")
