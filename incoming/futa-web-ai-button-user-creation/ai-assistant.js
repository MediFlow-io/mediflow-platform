(function () {
  "use strict";

  const quickTips = {
    bleeding:
      "Apply firm, direct pressure with clean cloth or gauze. Keep pressure on the wound and seek urgent medical help for heavy or uncontrolled bleeding.",
    burns:
      "Cool the burn under clean, cool running water for at least 20 minutes. Do not apply ice, butter, or creams, and seek medical help for serious burns.",
    choking:
      "If the person cannot speak, cough, or breathe, call emergency services and give five back blows followed by five abdominal thrusts. Use age-appropriate first aid for children and infants.",
    fainting:
      "Lay the person flat, raise their legs if there is no injury, loosen tight clothing, and check their breathing. Call emergency services if they do not recover quickly.",
    cpr:
      "If an adult is unresponsive and not breathing normally, call emergency services, start chest compressions, and use an AED if available. Follow the emergency operator's instructions."
  };

  const tipLabels = {
    bleeding: "Severe bleeding",
    burns: "Burns",
    choking: "Choking",
    fainting: "Fainting",
    cpr: "Unresponsive person"
  };

  function setResponse(element, text, type) {
    element.textContent = text;
    element.className = `assistant-response ${type || ""}`.trim();
  }

  function initialiseAssistant() {
    const button = document.getElementById("aiButton");
    const panel = document.getElementById("aiPanel");
    const tipSelect = document.getElementById("quickTipSelect");
    const tipButton = document.getElementById("quickTipButton");
    const responseElement = document.getElementById("aiResponse");
    const form = document.getElementById("aiForm");
    const questionInput = document.getElementById("aiQuestion");

    if (!button || !panel || !tipSelect || !tipButton || !responseElement || !form) {
      return;
    }

    button.addEventListener("click", () => {
      const isHidden = panel.hidden;
      panel.hidden = !isHidden;
      button.setAttribute("aria-expanded", String(isHidden));
      if (isHidden) {
        tipSelect.focus();
      }
    });

    tipButton.addEventListener("click", () => {
      setResponse(responseElement, quickTips[tipSelect.value], "success");
    });

    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      const question = questionInput.value.trim();

      if (!question) {
        setResponse(responseElement, "Enter a question first.", "error");
        return;
      }

      setResponse(responseElement, "Contacting the AI service...", "");

      try {
        const response = await fetch("/api/ai/ask", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "application/json"
          },
          credentials: "same-origin",
          body: JSON.stringify({ question })
        });
        const result = await response.json();

        if (!response.ok) {
          throw new Error(result.message || "The AI service could not answer.");
        }

        setResponse(
          responseElement,
          `${result.answer || "No answer was returned."} Always confirm medical decisions with a qualified clinician.`,
          "success"
        );
      } catch (error) {
        setResponse(
          responseElement,
          "The AI service is not available yet. Use the quick tips above for basic first aid and contact emergency services for urgent situations.",
          "error"
        );
      }
    });

    Object.keys(tipLabels).forEach((key) => {
      const option = document.createElement("option");
      option.value = key;
      option.textContent = tipLabels[key];
      tipSelect.appendChild(option);
    });
  }

  document.addEventListener("DOMContentLoaded", initialiseAssistant);
})();
