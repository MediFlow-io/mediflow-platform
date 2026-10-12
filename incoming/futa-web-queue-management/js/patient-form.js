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
  fields.forEach((field) => { data[field] = document.getElementById(field).value.trim(); });
  return data;
}

function fillForm(patient) {
  fields.forEach((field) => { document.getElementById(field).value = patient[field] || ""; });
}

function showMessage(text, type) {
  message.textContent = text;
  message.className = `message ${type}`;
}

function currentUser() {
  try { return JSON.parse(localStorage.getItem('mf_current_user')); } catch (e) { return null; }
}

function isAdmin() { const u = currentUser(); return u && u.role === 'admin'; }
function isDoctor() { const u = currentUser(); return u && u.role === 'doctor'; }
function isNurse() { const u = currentUser(); return u && u.role === 'nurse'; }

async function loadPatient() {
  const user = currentUser();
  if (user) {
    // personalise title
    if (!patientId) formTitle.textContent = isDoctor() ? 'Register patient (doctor)' : isNurse() ? 'View patient' : 'Register patient';
  }

  if (!patientId) {
    // new patient - doctors and admins can add, nurses cannot
    if (isNurse()) {
      showMessage('You do not have permission to add patients.', 'error');
      Array.from(patientForm.elements).forEach(el => el.disabled = true);
    }
    return;
  }

  formTitle.textContent = "Edit Patient";

  try {
    const response = await fetch(`/api/patients/${patientId}`);
    if (response.ok) {
      const patient = await response.json();
      fillForm(patient);
    } else {
      // fallback: try local demo storage
      const demo = JSON.parse(localStorage.getItem('mf_demo_patients') || '[]');
      const found = demo.find(p => String(p.id) === String(patientId));
      if (found) fillForm(found);
      else showMessage('Patient record could not be loaded.', 'error');
    }

    // Permissions: doctor cannot edit existing records
    if (isDoctor() && patientId) {
      showMessage('Doctors can create patients but not edit existing records in demo mode.', 'error');
      Array.from(patientForm.elements).forEach(el => el.disabled = true);
      return;
    }

    if (isNurse()) {
      showMessage('Nurse access: view-only.', 'error');
      Array.from(patientForm.elements).forEach(el => el.disabled = true);
      return;
    }

    // Admins can edit; show delete button if editing
    if (isAdmin() && patientId) {
      addDeleteButton();
    }
  } catch (err) {
    showMessage('Unable to load patient (demo mode).', 'error');
  }
}

function addDeleteButton() {
  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'button secondary';
  btn.style.marginLeft = '12px';
  btn.textContent = 'Delete patient';
  btn.addEventListener('click', async () => {
    // create a small confirm modal locally
    const ok = await (function(text){
      return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.style = 'position:fixed;inset:0;background:rgba(0,0,0,0.35);display:flex;align-items:center;justify-content:center;z-index:9999;';
        overlay.innerHTML = `<div style="background:#fff;padding:18px;border-radius:8px;max-width:420px;width:92%;box-shadow:0 10px 30px rgba(0,0,0,0.12);"><div style="margin-bottom:12px;color:#2b3e4f;font-weight:700">${text}</div><div style="text-align:right;"><button id=\"mf-cancel\" class=\"small-button\">Cancel</button> <button id=\"mf-ok\" class=\"button\">Delete</button></div></div>`;
        document.body.appendChild(overlay);
        overlay.querySelector('#mf-ok').addEventListener('click', () => { document.body.removeChild(overlay); resolve(true); });
        overlay.querySelector('#mf-cancel').addEventListener('click', () => { document.body.removeChild(overlay); resolve(false); });
      });
    })('Delete this patient? This cannot be undone.');

    if (!ok) return;
    // delete from demo store
    const demo = JSON.parse(localStorage.getItem('mf_demo_patients') || '[]');
    const remaining = demo.filter(p => String(p.id) !== String(patientId));
    localStorage.setItem('mf_demo_patients', JSON.stringify(remaining));
    showMessage('Patient removed (demo).', 'success');
    setTimeout(()=> window.location.href='dashboard.html', 500);
  });
  patientForm.querySelector('button[type=submit]').after(btn);
}

patientForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  if (isNurse()) { showMessage('You do not have permission to modify patient records.', 'error'); return; }
  if (isDoctor() && patientId) { showMessage('Doctors cannot edit existing records in demo mode.', 'error'); return; }

  const data = getFormData();
  const method = patientId ? "PUT" : "POST";
  const url = patientId ? `/api/patients/${patientId}` : "/api/patients";

  try {
    const response = await fetch(url, {
      method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data)
    });

    if (response.ok) {
      const result = await response.json();
      showMessage(result.message || 'Saved', 'success');
      if (!patientId) patientForm.reset();
      return;
    }

    // fallback demo storage
    const demo = JSON.parse(localStorage.getItem('mf_demo_patients') || '[]');
    if (patientId) {
      const updated = demo.map(p => String(p.id) === String(patientId) ? { ...p, ...data } : p);
      localStorage.setItem('mf_demo_patients', JSON.stringify(updated));
      showMessage('Patient updated (demo).', 'success');
    } else {
      const nextId = demo.length ? (Math.max(...demo.map(p => Number(p.id))) + 1) : 1001;
      const record = { id: String(nextId), hospitalNumber: `Q-${String(nextId).padStart(3, '0')}`, ...data };
      demo.push(record);
      localStorage.setItem('mf_demo_patients', JSON.stringify(demo));
      showMessage('Patient saved (demo).', 'success');
      patientForm.reset();
    }
  } catch (error) {
    showMessage(error.message || 'Unable to save patient', 'error');
  }
});

logoutButton.addEventListener("click", async () => {
  await fetch("/api/logout", { method: "POST" }).catch(()=>{});
  localStorage.removeItem('mf_current_user');
  window.location.href = "login.html";
});

loadPatient();
