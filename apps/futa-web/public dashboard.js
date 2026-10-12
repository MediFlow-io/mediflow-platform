const patientTableBody = document.getElementById("patientTableBody");
const searchInput = document.getElementById("searchInput");
const message = document.getElementById("message");
const logoutButton = document.getElementById("logoutButton");

async function loadPatients(search = "") {
  try {
    const response = await fetch(
      `/api/patients?search=${encodeURIComponent(search)}`
    );

    if (response.status === 401) {
      window.location.href = "login.html";
      return;
    }

    const patients = await response.json();
    patientTableBody.innerHTML = "";

    if (patients.length === 0) {
      patientTableBody.innerHTML = `
        <tr>
          <td colspan="6" class="empty">
            No patient records found.
          </td>
        </tr>
      `;
      return;
    }

    patients.forEach((patient) => {
      const row = document.createElement("tr");

      row.innerHTML = `
        <td>${escapeHtml(patient.hospitalNumber)}</td>
        <td>${escapeHtml(patient.fullName)}</td>
        <td>${escapeHtml(patient.sex)}</td>
        <td>${escapeHtml(patient.phone)}</td>
        <td>${escapeHtml(patient.diagnosis || "Not recorded")}</td>
        <td>
          <a
            class="small-button"
            href="patient-form.html?id=${patient.id}"
          >
            Edit
          </a>

          <button
            class="small-button danger"
            data-id="${patient.id}"
          >
            Delete
          </button>
        </td>
      `;

      patientTableBody.appendChild(row);
    });
  } catch (error) {
    showMessage("Unable to load patient records.", "error");
  }
}

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function showMessage(text, type) {
  message.textContent = text;
  message.className = `message ${type}`;
}

searchInput.addEventListener("input", () => {
  loadPatients(searchInput.value);
});

patientTableBody.addEventListener("click", async (event) => {
  if (!event.target.matches(".danger")) {
    return;
  }

  const patientId = event.target.dataset.id;

  const confirmed = confirm(
    "Delete this test patient record? This cannot be undone."
  );

  if (!confirmed) {
    return;
  }

  const response = await fetch(`/api/patients/${patientId}`, {
    method: "DELETE"
  });

  const result = await response.json();

  if (!response.ok) {
    showMessage(result.message, "error");
    return;
  }

  showMessage(result.message, "success");
  loadPatients(searchInput.value);
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", {
    method: "POST"
  });

  window.location.href = "login.html";
});

loadPatients();