/**
 * Assumptions:
 * - The parent form validates the completed OTP with the backend.
 * - onComplete is safe to call asynchronously and handles the six-digit code.
 * - Tailwind CSS is available for styling.
 */

import { useEffect, useId, useRef, useState } from "react";

/**
 * Accessible one-time-password input for multi-factor authentication.
 *
 * @param {{length?: number, onComplete: (code: string) => void, disabled?: boolean, error?: string}} props - Component props.
 * @returns {JSX.Element} OTP input group.
 */
export function MFAInput({
  length = 6,
  onComplete,
  disabled = false,
  error = "",
}) {
  const inputLength = Number.isInteger(length) && length > 0 ? length : 6;
  const [values, setValues] = useState(() => Array(inputLength).fill(""));
  const inputRefs = useRef([]);
  const lastCompletedCode = useRef(null);
  const errorId = useId();

  useEffect(() => {
    setValues(Array(inputLength).fill(""));
    lastCompletedCode.current = null;
    inputRefs.current[0]?.focus();
  }, [inputLength]);

  const completeIfReady = (nextValues) => {
    if (nextValues.every(Boolean)) {
      const code = nextValues.join("");
      if (code !== lastCompletedCode.current) {
        lastCompletedCode.current = code;
        onComplete(code);
      }
    } else {
      lastCompletedCode.current = null;
    }
  };

  const updateValue = (index, value) => {
    const digit = value.replace(/\D/g, "").slice(-1);
    const nextValues = [...values];
    nextValues[index] = digit;
    setValues(nextValues);

    if (digit && index < inputLength - 1) {
      inputRefs.current[index + 1]?.focus();
    }

    completeIfReady(nextValues);
  };

  const handleKeyDown = (event, index) => {
    if (event.key === "Backspace") {
      if (!values[index] && index > 0) {
        event.preventDefault();
        const nextValues = [...values];
        nextValues[index - 1] = "";
        setValues(nextValues);
        lastCompletedCode.current = null;
        inputRefs.current[index - 1]?.focus();
      }
      return;
    }

    if (event.key === "Delete") {
      event.preventDefault();
      updateValue(index, "");
      return;
    }

    if (event.key === "ArrowLeft" && index > 0) {
      event.preventDefault();
      inputRefs.current[index - 1]?.focus();
      return;
    }

    if (event.key === "ArrowRight" && index < inputLength - 1) {
      event.preventDefault();
      inputRefs.current[index + 1]?.focus();
      return;
    }

    if (
      event.key.length === 1 &&
      !/^[0-9]$/.test(event.key) &&
      !event.ctrlKey &&
      !event.metaKey
    ) {
      event.preventDefault();
    }
  };

  const handleBeforeInput = (event) => {
    if (event.data && /\D/.test(event.data)) {
      event.preventDefault();
    }
  };

  const handlePaste = (event) => {
    event.preventDefault();
    const pastedCode = event.clipboardData.getData("text").replace(/\D/g, "");
    if (pastedCode.length !== inputLength) {
      return;
    }

    const nextValues = pastedCode.split("");
    setValues(nextValues);
    inputRefs.current[inputLength - 1]?.focus();
    completeIfReady(nextValues);
  };

  return (
    <div>
      <div
        role="group"
        aria-label="Multi-factor authentication code"
        aria-invalid={Boolean(error)}
        aria-describedby={error ? errorId : undefined}
        className="flex gap-2"
      >
        {values.map((value, index) => (
          <input
            key={`${errorId}-${index}`}
            ref={(element) => {
              inputRefs.current[index] = element;
            }}
            type="text"
            inputMode="numeric"
            autoComplete={index === 0 ? "one-time-code" : "off"}
            maxLength={1}
            value={value}
            disabled={disabled}
            onChange={(event) => updateValue(index, event.target.value)}
            onKeyDown={(event) => handleKeyDown(event, index)}
            onBeforeInput={handleBeforeInput}
            onPaste={handlePaste}
            aria-label={`MFA digit ${index + 1} of ${inputLength}`}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? errorId : undefined}
            className="h-12 w-10 rounded border border-slate-300 text-center text-lg focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-200 disabled:cursor-not-allowed disabled:bg-slate-100"
          />
        ))}
      </div>
      {error ? (
        <p id={errorId} role="alert" className="mt-2 text-sm text-red-600">
          {error}
        </p>
      ) : null}
    </div>
  );
}

/**
 * Usage example in a login form:
 *
 * <MFAInput
 *   onComplete={(mfaCode) => login(email, password, mfaCode)}
 *   error={mfaError}
 *   disabled={isLoading}
 * />
 */
