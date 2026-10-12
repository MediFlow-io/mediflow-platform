/**
 * Assumptions:
 * - schema is a Zod schema compatible with validateWith().
 * - Form controls provide a name attribute for handleChange and handleBlur.
 * - onSubmit may return a promise and owns API-specific error handling.
 */

import { useCallback, useRef, useState } from "react";
import { validateWith } from "./schemas";

/**
 * Manage controlled form state and Zod validation.
 *
 * @param {import("zod").ZodType} schema - Zod schema used to validate form values.
 * @param {Record<string, *>} initialValues - Initial controlled form values.
 * @param {(validatedData: *) => void|Promise<void>} onSubmit - Validated submission callback.
 * @returns {{values: Record<string, *>, errors: Record<string, string[]>, touched: Record<string, boolean>, handleChange: (event: Event) => void, handleBlur: (event: Event) => void, handleSubmit: (event?: Event) => Promise<boolean>, isSubmitting: boolean, submitError: string|null, reset: () => void}}
 *   Form state, event handlers, submission state, and reset behavior.
 *
 * @example
 * import { userLoginSchema } from "./schemas";
 * import { useFormValidation } from "./useFormValidation";
 *
 * function LoginForm({ login }) {
 *   const form = useFormValidation(
 *     userLoginSchema,
 *     { email: "", password: "", mfaCode: "" },
 *     (values) => login(values.email, values.password, values.mfaCode),
 *   );
 *
 *   return (
 *     <form onSubmit={form.handleSubmit} noValidate>
 *       <input name="email" value={form.values.email} onChange={form.handleChange} onBlur={form.handleBlur} />
 *       {form.touched.email && form.errors.email?.[0]}
 *       <input name="password" type="password" value={form.values.password} onChange={form.handleChange} onBlur={form.handleBlur} />
 *       {form.touched.password && form.errors.password?.[0]}
 *       {form.submitError && <p role="alert">{form.submitError}</p>}
 *       <button type="submit" disabled={form.isSubmitting}>Sign in</button>
 *     </form>
 *   );
 * }
 */
export function useFormValidation(schema, initialValues, onSubmit) {
  const initialValuesRef = useRef({ ...initialValues });
  const [values, setValues] = useState(() => ({ ...initialValuesRef.current }));
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState(null);

  const handleChange = useCallback((event) => {
    const { name, type, value, checked } = event.target;
    const nextValue = type === "checkbox" ? checked : value;

    setValues((currentValues) => ({
      ...currentValues,
      [name]: nextValue,
    }));
    setErrors((currentErrors) => {
      if (!(name in currentErrors)) {
        return currentErrors;
      }

      const nextErrors = { ...currentErrors };
      delete nextErrors[name];
      return nextErrors;
    });
    setSubmitError(null);
  }, []);

  const handleBlur = useCallback((event) => {
    const { name } = event.target;
    setTouched((currentTouched) => ({
      ...currentTouched,
      [name]: true,
    }));
  }, []);

  const handleSubmit = useCallback(async (event) => {
    event?.preventDefault();
    setSubmitError(null);

    const result = validateWith(schema, values);
    if (!result.success) {
      setErrors(result.errors || {});
      setTouched((currentTouched) => ({
        ...currentTouched,
        ...Object.keys(values).reduce(
          (nextTouched, fieldName) => ({ ...nextTouched, [fieldName]: true }),
          {},
        ),
      }));
      return false;
    }

    setErrors({});
    setIsSubmitting(true);

    try {
      await onSubmit(result.data);
      return true;
    } catch (error) {
      setSubmitError(
        error instanceof Error && error.message
          ? error.message
          : "Unable to submit the form.",
      );
      return false;
    } finally {
      setIsSubmitting(false);
    }
  }, [onSubmit, schema, values]);

  const reset = useCallback(() => {
    setValues({ ...initialValuesRef.current });
    setErrors({});
    setTouched({});
    setIsSubmitting(false);
    setSubmitError(null);
  }, []);

  return {
    values,
    errors,
    touched,
    handleChange,
    handleBlur,
    handleSubmit,
    isSubmitting,
    submitError,
    reset,
  };
}
