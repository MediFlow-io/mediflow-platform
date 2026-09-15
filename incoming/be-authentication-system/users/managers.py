from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError


class CustomUserManager(BaseUserManager):
    """
    Custom manager for MediFlow User model where unique_id (Matric No or Staff ID)
    serves as the unique username field for authentication.
    """

    def create_user(self, unique_id, email, password=None, role=None, **extra_fields):
        """
        Create and return a regular user with unique_id, email, role, and password.
        Enforces Django's password validators when password is provided.
        """
        if not unique_id:
            raise ValueError('The Unique ID (Matric No or Staff ID) must be provided.')
        if not email:
            raise ValueError('An email address must be provided.')

        email = self.normalize_email(email)
        unique_id = str(unique_id).strip()

        if not role:
            role = extra_fields.pop('role', 'Student')

        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        user = self.model(
            unique_id=unique_id,
            email=email,
            role=role,
            **extra_fields
        )

        if password:
            # Enforce Django password validators
            validate_password(password, user=user)
            user.set_password(password)
        else:
            user.set_unusable_password()

        user.save(using=self._db)
        return user

    def create_superuser(self, unique_id, email, password=None, **extra_fields):
        """
        Create and return a superuser with admin privileges and Admin role.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('role', 'Admin')

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self.create_user(unique_id, email, password, **extra_fields)
