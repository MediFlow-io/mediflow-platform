const patientTableBody = document.getElementById("patientTableBody");
const searchInput = document.getElementById("searchInput");
const message = document.getElementById("message");
const logoutButton = document.getElementById("logoutButton");
const AUTH_KEY = "futa-hospital-auth";

function ensureAuthenticated() {
  const auth = JSON.parse(localStorage.getItem(AUTH_KEY) || "null");

  if (!auth) {
    window.location.href = "login.html";
    return false;
  }

  return true;
}

function readPatients() {
  return JSON.parse(localStorage.getItem("futa-hospital-patients") || "[]");
}

function writePatients(patients) {
  localStorage.setItem("futa-hospital-patients", JSON.stringify(patients));
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

function loadPatients(search = "") {
  if (!ensureAuthenticated()) {
    return;
  }

  const patients = readPatients();
  const normalizedSearch = search.trim().toLowerCase();
  const filteredPatients = normalizedSearch
    ? patients.filter((patient) => {
        const searchableValues = [
          patient.hospitalNumber,
          patient.fullName,
          patient.sex,
          patient.phone,
          patient.diagnosis
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase();

        return searchableValues.includes(normalizedSearch);
      })
    : patients;

  patientTableBody.innerHTML = "";

  if (filteredPatients.length === 0) {
    patientTableBody.innerHTML = `
      <tr>
        <td colspan="6" class="empty">
          No patient records found.
        </td>
      </tr>
    `;
    return;
  }

  filteredPatients.forEach((patient) => {
    const row = document.createElement("tr");

    row.innerHTML = `
      <td>${escapeHtml(patient.hospitalNumber || "N/A")}</td>
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
}

searchInput.addEventListener("input", () => {
  loadPatients(searchInput.value);
});

patientTableBody.addEventListener("click", (event) => {
  if (!event.target.matches(".danger")) {
    return;
  }

  const patientId = event.target.dataset.id;
  const confirmed = confirm(
    "Delete this patient record? This cannot be undone."
  );

  if (!confirmed) {
    return;
  }

  const patients = readPatients();
  const updatedPatients = patients.filter((patient) => patient.id !== patientId);
  writePatients(updatedPatients);

  showMessage("Patient record deleted successfully.", "success");
  loadPatients(searchInput.value);
});

logoutButton.addEventListener("click", () => {
  localStorage.removeItem(AUTH_KEY);
  window.location.href = "login.html";
});

loadPatients();
