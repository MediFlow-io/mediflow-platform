const studentForm = document.getElementById("studentForm");
const message = document.getElementById("message");
const logoutButton = document.getElementById("logoutButton");

function showMessage(text, type) {
  message.textContent = text;
  message.className = `message ${type || ""}`.trim();
}

studentForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const account = {
    staffId: document.getElementById("studentId").value.trim(),
    password: document.getElementById("password").value,
    confirmPassword: document.getElementById("confirmPassword").value
  };
  const validation = AccountValidation.validateAccount(account);

  if (!validation.valid) {
    showMessage(validation.errors.join(" "), "error");
    return;
  }

  const fullName = document.getElementById("fullName").value.trim();
  if (!fullName) {
    showMessage("Student name is required.", "error");
    return;
  }

  showMessage("Creating student account...", "");

  try {
    const response = await fetch("/api/admin/users", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json"
      },
      credentials: "same-origin",
      body: JSON.stringify({
        staffId: account.staffId,
        fullName,
        password: account.password,
        role: "student"
      })
    });
    const result = await response.json();

    if (response.status === 401) {
      window.location.replace("login.html");
      return;
    }
    if (response.status === 403) {
      showMessage("Only an administrator can create student accounts.", "error");
      return;
    }
    if (!response.ok) {
      throw new Error(result.message || "Student account creation failed.");
    }

    showMessage(result.message || "Student account created successfully.", "success");
    studentForm.reset();
  } catch (error) {
    showMessage(
      error.message === "Failed to fetch"
        ? "The account service is not available. Start the backend and try again."
        : error.message,
      "error"
    );
  }
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST", credentials: "same-origin" });
  window.location.replace("login.html");
});
