const loginForm = document.getElementById("loginForm");
const message = document.getElementById("message");

const AUTH_KEY = "futa-hospital-auth";

function getStoredPatients() {
  return JSON.parse(localStorage.getItem("futa-hospital-patients") || "[]");
}

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();

  const staffId = document.getElementById("staffId").value.trim();
  const password = document.getElementById("password").value;

  message.textContent = "Logging in...";
  message.className = "message";

  try {
    const response = await fetch("/api/login", {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        staffId,
        password
      })
    });

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.message);
    }

    message.textContent = result.message;
    message.className = "message success";

  setTimeout(() => {
    window.location.href = "dashboard.html";
  }, 500);
});
