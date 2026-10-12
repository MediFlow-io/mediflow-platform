const patientForm = document.getElementById("patientForm");
const formTitle = document.getElementById("formTitle");
const message = document.getElementById("message");
const logoutButton = document.getElementById("logoutButton");

const params = new URLSearchParams(window.location.search);
const patientId = params.get("id");
const AUTH_KEY = "futa-hospital-auth";

const fields = [
  "fullName",
  "dateOfBirth",
  "sex",
  "phone",
  "address",
  "nextOfKin",
  "nextOfKinPhone",
  "allergies",
  "medicalHistory",
  "complaint",
  "diagnosis",
  "treatment",
  "notes"
];

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

function getFormData() {
  const data = {};

  fields.forEach((field) => {
    data[field] = document.getElementById(field).value.trim();
  });

  return data;
}

function fillForm(patient) {
  fields.forEach((field) => {
    document.getElementById(field).value = patient[field] || "";
  });
}

function showMessage(text, type) {
  message.textContent = text;
  message.className = `message ${type}`;
}

function loadPatient() {
  if (!ensureAuthenticated()) {
    return;
  }

  if (!patientId) {
    return;
  }

  formTitle.textContent = "Edit Patient";

  const patient = readPatients().find((entry) => entry.id === patientId);

  if (!patient) {
    showMessage("Patient record could not be loaded.", "error");
    return;
  }

  fillForm(patient);
}

patientForm.addEventListener("submit", (event) => {
  event.preventDefault();

  if (!ensureAuthenticated()) {
    return;
  }

  const data = getFormData();

  if (!data.fullName || !data.sex || !data.phone) {
    showMessage("Please fill in the required fields.", "error");
    return;
  }

  const patients = readPatients();
  const timestamp = new Date().toISOString();

  if (patientId) {
    const index = patients.findIndex((entry) => entry.id === patientId);

    if (index === -1) {
      showMessage("Patient record could not be found.", "error");
      return;
    }

    patients[index] = {
      ...patients[index],
      ...data,
      updatedAt: timestamp
    };

    writePatients(patients);
    showMessage("Patient updated successfully.", "success");
    return;
  }

  const newPatient = {
    id: `patient-${Date.now()}`,
    hospitalNumber: `FUTA-${String(Date.now()).slice(-6)}`,
    createdAt: timestamp,
    updatedAt: timestamp,
    ...data
  };

  patients.push(newPatient);
  writePatients(patients);
  showMessage("Patient saved successfully.", "success");
  patientForm.reset();
});

logoutButton.addEventListener("click", () => {
  localStorage.removeItem(AUTH_KEY);
  window.location.href = "login.html";
});

loadPatient();
