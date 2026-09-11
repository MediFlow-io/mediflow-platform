const registerForm = document.getElementById("registerForm");
const registerMessage = document.getElementById("message");

registerForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const account = {
    staffId: document.getElementById("staffId").value,
    password: document.getElementById("password").value,
    confirmPassword: document.getElementById("confirmPassword").value
  };
  const validation = AccountValidation.validateAccount(account);

  if (!validation.valid) {
    registerMessage.textContent = validation.errors.join(" ");
    registerMessage.className = "message error";
    return;
  }

  registerMessage.textContent = "Creating account...";
  registerMessage.className = "message";

  try {
    const response = await fetch("/api/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin",
      body: JSON.stringify({
        username: account.staffId.trim(),
        password: account.password
      })
    });
    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message || "Account creation failed.");
    }

    registerMessage.textContent = result.message || "Account created successfully.";
    registerMessage.className = "message success";
    registerForm.reset();
  } catch (error) {
    registerMessage.textContent = error.message;
    registerMessage.className = "message error";
  }
});
