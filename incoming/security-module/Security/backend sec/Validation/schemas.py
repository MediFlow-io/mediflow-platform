"""Pydantic input validation schemas for the healthcare application.

Every endpoint MUST validate input with one of these schemas.

This module centralizes request validation so that invalid user input is rejected
before business logic or database writes occur. These models enforce typed input,
field constraints, and custom validation rules consistent with healthcare data
quality and security requirements.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator


class BaseSecuritySchema(BaseModel):
    """Base schema for all request models.

    This base class applies strict validation rules across all endpoint inputs.
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        validate_assignment=True,
    )


class UserRegisterSchema(BaseSecuritySchema):
    """Schema for user self-registration or staff registration."""

    email: EmailStr = Field(..., min_length=6, max_length=255)
    password: str = Field(..., min_length=12, max_length=128)
    full_name: str = Field(..., min_length=2, max_length=120)
    role: str = Field(..., min_length=3, max_length=40)
    phone: str = Field(..., min_length=7, max_length=20)

    @field_validator("full_name")
    @classmethod
    def validate_full_name(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("full_name cannot be blank")
        return value

    @field_validator("role")
    @classmethod
    def validate_role(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"student", "staff", "nurse", "doctor", "admin"}
        if normalized not in allowed:
            raise ValueError("role must be one of: student, staff, nurse, doctor, admin")
        return normalized

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, value: str) -> str:
        cleaned = value.replace(" ", "").replace("-", "")
        if not cleaned.isdigit():
            raise ValueError("phone must contain only digits")
        return value


class UserLoginSchema(BaseSecuritySchema):
    """Schema for login requests."""

    email: EmailStr = Field(..., min_length=6, max_length=255)
    password: str = Field(..., min_length=12, max_length=128)
    mfa_code: str | None = Field(default=None, min_length=6, max_length=8)

    @field_validator("mfa_code")
    @classmethod
    def validate_mfa_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.isdigit():
            raise ValueError("mfa_code must be numeric")
        return value


class PasswordResetRequestSchema(BaseSecuritySchema):
    """Schema for password-reset email submissions."""

    email: EmailStr = Field(..., min_length=6, max_length=255)


class PasswordResetSchema(BaseSecuritySchema):
    """Schema for password resets using a token."""

    token: str = Field(..., min_length=16, max_length=512)
    new_password: str = Field(..., min_length=12, max_length=128)

    @field_validator("token")
    @classmethod
    def validate_token(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("token cannot be blank")
        return value


class AppointmentCreateSchema(BaseSecuritySchema):
    """Schema for creating a medical appointment."""

    doctor_id: str = Field(..., min_length=1, max_length=128)
    reason: str = Field(..., min_length=5, max_length=500)
    preferred_date: datetime = Field(...)

    @field_validator("doctor_id")
    @classmethod
    def validate_doctor_id(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("doctor_id cannot be blank")
        return value

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("reason cannot be blank")
        return value

    @field_validator("preferred_date")
    @classmethod
    def validate_future_date(cls, value: datetime) -> datetime:
        if value <= datetime.utcnow():
            raise ValueError("preferred_date must be in the future")
        return value


class AppointmentUpdateSchema(BaseSecuritySchema):
    """Schema for appointment status updates or notes."""

    status: str = Field(..., min_length=2, max_length=40)
    notes: str | None = Field(default=None, max_length=1000)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        allowed = {"scheduled", "confirmed", "cancelled", "completed", "rescheduled"}
        normalized = value.strip().lower()
        if normalized not in allowed:
            raise ValueError("status must be a valid appointment status")
        return normalized

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if value.strip() == "":
            raise ValueError("notes cannot be blank when provided")
        return value


class MedicalRecordSchema(BaseSecuritySchema):
    """Schema for medical record creation or updates."""

    patient_id: str = Field(..., min_length=1, max_length=128)
    notes: str = Field(..., min_length=5, max_length=2000)
    diagnosis: str = Field(..., min_length=2, max_length=500)

    @field_validator("patient_id")
    @classmethod
    def validate_patient_id(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("patient_id cannot be blank")
        return value

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("notes cannot be blank")
        return value

    @field_validator("diagnosis")
    @classmethod
    def validate_diagnosis(cls, value: str) -> str:
        if value.strip() == "":
            raise ValueError("diagnosis cannot be blank")
        return value


__all__ = [
    "UserRegisterSchema",
    "UserLoginSchema",
    "PasswordResetRequestSchema",
    "PasswordResetSchema",
    "AppointmentCreateSchema",
    "AppointmentUpdateSchema",
    "MedicalRecordSchema",
]
