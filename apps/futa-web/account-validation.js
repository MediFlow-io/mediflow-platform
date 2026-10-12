(function (root, factory) {
  if (typeof module === "object" && module.exports) {
    module.exports = factory();
  } else {
    root.AccountValidation = factory();
  }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  const COMMON_PASSWORDS = new Set([
    "123456789012",
    "password1234",
    "qwertyuiop12",
    "admin1234567",
    "letmein12345"
  ]);

  function validateAccount(account) {
    const errors = [];
    const staffId = typeof account.staffId === "string" ? account.staffId.trim() : "";
    const password = typeof account.password === "string" ? account.password : "";
    const confirmPassword =
      typeof account.confirmPassword === "string" ? account.confirmPassword : "";

    if (!/^[A-Za-z0-9._-]{3,64}$/.test(staffId)) {
      errors.push("Staff ID must be 3-64 characters and contain only letters, numbers, ., _, or -.");
    }

    if (password.length < 12) {
      errors.push("Password must be at least 12 characters long.");
    }
    if (/\s/.test(password)) {
      errors.push("Password must not contain spaces.");
    }
    if (!/[a-z]/.test(password)) {
      errors.push("Password must contain a lowercase letter.");
    }
    if (!/[A-Z]/.test(password)) {
      errors.push("Password must contain an uppercase letter.");
    }
    if (!/[0-9]/.test(password)) {
      errors.push("Password must contain a number.");
    }
    if (!/[^A-Za-z0-9]/.test(password)) {
      errors.push("Password must contain a special character.");
    }
    if (COMMON_PASSWORDS.has(password.toLowerCase())) {
      errors.push("Password is too common.");
    }
    if (staffId && password.toLowerCase().includes(staffId.toLowerCase())) {
      errors.push("Password must not contain the staff ID.");
    }
    if (password !== confirmPassword) {
      errors.push("Passwords do not match.");
    }

    return {
      valid: errors.length === 0,
      errors
    };
  }

  return { validateAccount };
});
