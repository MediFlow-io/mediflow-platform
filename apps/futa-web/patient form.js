const patientForm = document.getElementById("patientForm");
const formTitle = document.getElementById("formTitle");
const message = document.getElementById("message");
const logoutButton = document.getElementById("logoutButton");

const params = new URLSearchParams(window.location.search);
const patientId = params.get("id");

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

async function loadPatient() {
  if (!patientId) {
    return;
  }

  formTitle.textContent = "Edit Patient";

  const response = await fetch(`/api/patients/${patientId}`);

  if (response.status === 401) {
    window.location.href = "login.html";
    return;
  }

  if (!response.ok) {
    showMessage("Patient record could not be loaded.", "error");
    return;
  }

  const patient = await response.json();
  fillForm(patient);
}

patientForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  const data = getFormData();
  const method = patientId ? "PUT" : "POST";
  const url = patientId
    ? `/api/patients/${patientId}`
    : "/api/patients";

  try {
    const response = await fetch(url, {
      method,
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (response.status === 401) {
      window.location.href = "login.html";
      return;
    }

    if (!response.ok) {
      throw new Error(result.message);
    }

    showMessage(result.message, "success");

    if (!patientId) {
      patientForm.reset();
    }
  } catch (error) {
    showMessage(error.message, "error");
  }
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", {
    method: "POST"
  });

  window.location.href = "login.html";
});

loadPatient();