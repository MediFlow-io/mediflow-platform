(function () {
  "use strict";

  const tips = {
    bleeding: "Apply firm pressure with clean cloth or gauze. Seek urgent help if bleeding is heavy or does not stop.",
    burns: "Cool a burn under clean, cool running water for at least 20 minutes. Do not use ice, butter, or creams.",
    choking: "If the person cannot speak, cough, or breathe, call emergency services and use age-appropriate choking first aid.",
    fainting: "Lay the person flat, check breathing, and call emergency services if they do not recover quickly."
  };

  function addWidget() {
    if (document.getElementById("aiWidget")) return;
    const widget = document.createElement("aside");
    widget.id = "aiWidget";
    widget.className = "ai-widget";
    widget.innerHTML = `
      <button id="aiWidgetToggle" class="ai-widget-toggle" type="button" aria-expanded="false">
        <span aria-hidden="true">✦</span> AI help
      </button>
      <div id="aiWidgetPanel" class="ai-widget-panel" hidden>
        <div class="ai-widget-header">
          <strong>AI tips & enquiries</strong>
          <button id="aiWidgetClose" type="button" aria-label="Close AI help">×</button>
        </div>
        <label for="aiWidgetTip">Quick tip</label>
        <select id="aiWidgetTip">
          <option value="bleeding">Severe bleeding</option>
          <option value="burns">Burns</option>
          <option value="choking">Choking</option>
          <option value="fainting">Fainting</option>
        </select>
        <button id="aiWidgetShowTip" class="small-button" type="button">Show tip</button>
        <form id="aiWidgetForm">
          <label for="aiWidgetQuestion">Ask an enquiry</label>
          <input id="aiWidgetQuestion" maxlength="500" placeholder="Ask a general question" required>
          <button class="button" type="submit">Ask AI</button>
        </form>
        <p id="aiWidgetResponse" class="ai-widget-response" role="status" aria-live="polite"></p>
        <small>General information only, not a diagnosis.</small>
      </div>
    `;
    document.body.appendChild(widget);

    const panel = document.getElementById("aiWidgetPanel");
    const toggle = document.getElementById("aiWidgetToggle");
    const response = document.getElementById("aiWidgetResponse");
    const setResponse = (text, type) => {
      response.textContent = text;
      response.className = `ai-widget-response ${type || ""}`.trim();
    };
    const open = () => {
      panel.hidden = false;
      toggle.setAttribute("aria-expanded", "true");
    };
    const close = () => {
      panel.hidden = true;
      toggle.setAttribute("aria-expanded", "false");
    };
    toggle.addEventListener("click", () => (panel.hidden ? open() : close()));
    document.getElementById("aiWidgetClose").addEventListener("click", close);
    document.getElementById("aiWidgetShowTip").addEventListener("click", () => {
      setResponse(tips[document.getElementById("aiWidgetTip").value], "success");
    });
    document.getElementById("aiWidgetForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = document.getElementById("aiWidgetQuestion").value.trim();
      setResponse("Getting an answer...", "");
      try {
        const result = await fetch("/api/ai/ask", {
          method: "POST",
          headers: { "Content-Type": "application/json", Accept: "application/json" },
          credentials: "same-origin",
          body: JSON.stringify({ question })
        });
        const body = await result.json();
        if (!result.ok) throw new Error(body.message || "The AI service could not answer.");
        setResponse(body.answer, "success");
      } catch (error) {
        setResponse(error.message || "The AI service is unavailable.", "error");
      }
    });
  }

  document.addEventListener("DOMContentLoaded", async () => {
    try {
      const response = await fetch("/api/session", { credentials: "same-origin" });
      if (response.ok) addWidget();
    } catch {
      // The auth guard owns navigation when the session cannot be checked.
    }
  });
})();
