/**
 * Assumptions:
 * - Field names match the frontend API payloads (camelCase).
 * - Backend/security/Validation/schemas.py remains the authoritative contract.
 * - Trim string values before submitting; frontend validation improves UX only.
 *
 * Frontend validation improves UX. Backend MUST re-validate everything.
 * Never trust the frontend.
 */

import { z } from "zod";

const ROLE_VALUES = ["student", "staff", "nurse", "doctor", "admin"];
const APPOINTMENT_STATUS_VALUES = [
  "scheduled",
  "confirmed",
  "cancelled",
  "completed",
  "rescheduled",
];

/** User registration payload schema. */
export const userRegisterSchema = z.object({
  email: z.string().trim().min(6).max(255).email(),
  password: z.string().trim().min(12).max(128),
  fullName: z.string().trim().min(2).max(120),
  role: z.enum(ROLE_VALUES),
  phone: z.string().trim().min(7).max(20).regex(/^\d+$/, "Phone must contain only digits"),
});

/** User login payload schema. */
export const userLoginSchema = z.object({
  email: z.string().trim().min(6).max(255).email(),
  password: z.string().trim().min(12).max(128),
  mfaCode: z.string().trim().regex(/^\d{6}$/, "MFA code must contain 6 digits").optional(),
});

/** Password-reset request schema. */
export const passwordResetRequestSchema = z.object({
  email: z.string().trim().min(6).max(255).email(),
});

/** Password-reset submission schema. */
export const passwordResetSchema = z.object({
  token: z.string().trim().min(16).max(512),
  newPassword: z.string().trim().min(12).max(128),
});

/** Appointment creation schema. */
export const appointmentCreateSchema = z.object({
  doctorId: z.string().trim().uuid(),
  reason: z.string().trim().min(10).max(500),
  preferredDate: z.coerce.date().refine(
    (date) => date.getTime() > Date.now(),
    "Preferred date must be in the future",
  ),
});

/** Appointment update schema. */
export const appointmentUpdateSchema = z.object({
  status: z.enum(APPOINTMENT_STATUS_VALUES),
  notes: z.string().trim().max(1000).optional(),
});

/** Medical-record schema. */
export const medicalRecordSchema = z.object({
  patientId: z.string().trim().uuid(),
  notes: z.string().trim().min(5).max(2000),
  diagnosis: z.string().trim().min(2).max(500),
});

/**
 * Validate data with a Zod schema and return a predictable result shape.
 *
 * @param {import("zod").ZodType} schema - Schema used for validation.
 * @param {*} data - Input data to validate.
 * @returns {{success: true, data: *, errors: null}|{success: false, data: null, errors: Record<string, string[]>}}
 *   Parsed data on success or field-level validation errors on failure.
 */
export function validateWith(schema, data) {
  const result = schema.safeParse(data);

  if (result.success) {
    return {
      success: true,
      data: result.data,
      errors: null,
    };
  }

  return {
    success: false,
    data: null,
    errors: result.error.flatten().fieldErrors,
  };
}

/**
 * Usage example:
 *
 * const result = validateWith(userLoginSchema, formValues);
 * if (!result.success) {
 *   setErrors(result.errors);
 * } else {
 *   await login(result.data.email, result.data.password, result.data.mfaCode);
 * }
 */
