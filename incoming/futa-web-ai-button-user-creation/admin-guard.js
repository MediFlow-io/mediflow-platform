(function () {
  "use strict";

  fetch("/api/session", {
    credentials: "same-origin",
    headers: { Accept: "application/json" }
  })
    .then(async (response) => {
      if (!response.ok) {
        window.location.replace("login.html");
        return;
      }

      const session = await response.json();
      const role = session.role || (session.user && session.user.role);

      if (role !== "admin") {
        window.location.replace("dashboard.html");
      }
    })
    .catch(() => {
      window.location.replace("login.html");
    });
})();
