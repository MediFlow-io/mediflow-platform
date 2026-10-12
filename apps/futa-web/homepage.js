document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".topbar").forEach((topbar) => {
    if (topbar.querySelector(".futa-header-logo")) return;

    const logo = document.createElement("img");
    logo.className = "futa-header-logo";
    logo.src = "futa logo.jpg";
    logo.alt = "Federal University of Technology Akure logo";
    topbar.appendChild(logo);
  });

  const toggleButton = document.querySelector(".theme-toggle");
  if (!toggleButton) return;

  const themeIcon = toggleButton.querySelector(".theme-icon");
  const themeText = toggleButton.querySelector(".theme-text");

  const applyTheme = (theme) => {
    document.body.dataset.theme = theme;
    localStorage.setItem("theme-preference", theme);

    if (themeIcon) {
      themeIcon.textContent = theme === "dark" ? "☀️" : "🌙";
    }

    if (themeText) {
      themeText.textContent = theme === "dark" ? "Light mode" : "Dark mode";
    }

    toggleButton.setAttribute(
      "aria-label",
      theme === "dark" ? "Switch to light mode" : "Switch to dark mode"
    );
  };

  const savedTheme = localStorage.getItem("theme-preference");
  const preferredTheme =
    savedTheme || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");

  applyTheme(preferredTheme);

  toggleButton.addEventListener("click", () => {
    const nextTheme = document.body.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(nextTheme);
  });
});
