const loginForm = document.getElementById("loginForm");
const message = document.getElementById("message");

loginForm.addEventListener("submit", async (event) => {
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
  } catch (error) {
    message.textContent = error.message;
    message.className = "message error";
  }
});