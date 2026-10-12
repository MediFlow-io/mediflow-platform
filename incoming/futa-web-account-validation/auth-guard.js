(function () {
  "use strict";

  fetch("/api/me", {
    credentials: "same-origin",
    headers: { Accept: "application/json" }
  })
    .then((response) => {
      if (!response.ok) {
        window.location.replace("login.html");
      }
    })
    .catch(() => {
      window.location.replace("login.html");
    });
})();
