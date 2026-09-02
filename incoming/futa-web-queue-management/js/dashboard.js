const patientTableBody = document.getElementById("patientTableBody");
const searchInput = document.getElementById("searchInput");
const priorityFilter = document.getElementById("priorityFilter");
const message = document.getElementById("message");
const logoutButton = document.getElementById("logoutButton");
const refreshQueue = document.getElementById("refreshQueue");
const registerLink = document.getElementById('registerLink');
const userMgmtLink = document.getElementById('userMgmtLink');

const demoQueue = [
  { id: "1", fullName: "Amina Yusuf", hospitalNumber: "Q-001", sex: "F", priority: 1, arrival: "08:42", wait: "Now", status: "Urgent" },
  { id: "2", fullName: "Chinedu Okafor", hospitalNumber: "Q-002", sex: "M", priority: 2, arrival: "08:47", wait: "5 min", status: "Urgent" },
  { id: "3", fullName: "Fatima Bello", hospitalNumber: "Q-003", sex: "F", priority: 3, arrival: "08:51", wait: "12 min", status: "Waiting" },
  { id: "4", fullName: "Samuel Adeyemi", hospitalNumber: "Q-004", sex: "M", priority: 3, arrival: "08:55", wait: "18 min", status: "Waiting" },
  { id: "5", fullName: "Grace Eze", hospitalNumber: "Q-005", sex: "F", priority: 4, arrival: "09:02", wait: "25 min", status: "Waiting" },
  { id: "6", fullName: "Ibrahim Musa", hospitalNumber: "Q-006", sex: "M", priority: 5, arrival: "09:08", wait: "31 min", status: "Waiting" }
];

let queue = demoQueue;

function currentUser() { try { return JSON.parse(localStorage.getItem('mf_current_user')); } catch(e){return null;} }
function isAdmin(){ const u=currentUser(); return u && u.role==='admin'; }
function isDoctor(){ const u=currentUser(); return u && u.role==='doctor'; }
function isNurse(){ const u=currentUser(); return u && u.role==='nurse'; }

function escapeHtml(value) {
  return String(value || "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
}

// Simple confirmation modal used instead of window.confirm for better UX
function createConfirmModal() {
  if (document.getElementById('mf-confirm-modal')) return;
  const overlay = document.createElement('div');
  overlay.id = 'mf-confirm-modal';
  overlay.style = 'position:fixed;inset:0;background:rgba(0,0,0,0.35);display:flex;align-items:center;justify-content:center;z-index:9999;';
  overlay.innerHTML = `
    <div style="background:#fff;padding:18px;border-radius:8px;max-width:420px;width:92%;box-shadow:0 10px 30px rgba(0,0,0,0.12);">
      <div id="mf-confirm-text" style="margin-bottom:12px;color:#2b3e4f;font-weight:700"></div>
      <div style="text-align:right;">
        <button id="mf-confirm-cancel" class="small-button" style="margin-right:8px;">Cancel</button>
        <button id="mf-confirm-ok" class="button">Confirm</button>
      </div>
    </div>
  `;
  document.body.appendChild(overlay);
  overlay.querySelector('#mf-confirm-cancel').addEventListener('click', () => overlay.style.display = 'none');
}

function showConfirm(text) {
  return new Promise((resolve) => {
    createConfirmModal();
    const overlay = document.getElementById('mf-confirm-modal');
    overlay.querySelector('#mf-confirm-text').textContent = text;
    overlay.style.display = 'flex';
    const ok = overlay.querySelector('#mf-confirm-ok');
    const cancel = overlay.querySelector('#mf-confirm-cancel');

    function done(val) {
      overlay.style.display = 'none';
      ok.removeEventListener('click', onOk);
      cancel.removeEventListener('click', onCancel);
      resolve(val);
    }
    function onOk() { done(true); }
    function onCancel() { done(false); }
    ok.addEventListener('click', onOk);
    cancel.addEventListener('click', onCancel);
  });
}

function renderQueue() {
  const query = searchInput.value.trim().toLowerCase();
  const filter = priorityFilter.value;
  const filtered = queue.filter((patient) => {
    const matchesSearch = !query || `${patient.fullName} ${patient.hospitalNumber}`.toLowerCase().includes(query);
    const matchesFilter = filter === "all" || (filter === "urgent" && patient.priority <= 2) || (filter === "waiting" && patient.status === "Waiting");
    return matchesSearch && matchesFilter;
  });

  const allowDelete = isAdmin();

  patientTableBody.innerHTML = filtered.length ? filtered.map((patient) => `
    <tr>
      <td><div class="patient-cell"><span class="avatar">${escapeHtml(patient.fullName.split(" ").map((part) => part[0]).join("").slice(0, 2))}</span><div>${isAdmin() ? `<a href="patient-form.html?id=${encodeURIComponent(patient.id)}"><strong>${escapeHtml(patient.fullName)}</strong></a>` : `<strong>${escapeHtml(patient.fullName)}</strong>`}<small>${escapeHtml(patient.sex)} · OPD</small></div></div></td>
      <td><strong class="queue-number">${escapeHtml(patient.hospitalNumber)}</strong></td>
      <td><span class="priority-badge ${patient.priority <= 2 ? "urgent" : "standard"}">ESI ${patient.priority} · ${patient.priority <= 2 ? "Urgent" : "Standard"}</span></td>
      <td>${escapeHtml(patient.arrival)}</td><td>${escapeHtml(patient.wait)}</td>
      <td><span class="status-badge ${patient.status.toLowerCase()}"><i></i>${escapeHtml(patient.status)}</span></td>
      <td>
        <a class="row-action" href="patient-form.html?id=${encodeURIComponent(patient.id)}">View</a>
        ${allowDelete ? `<button data-id="${encodeURIComponent(patient.id)}" class="small-button danger row-delete">Delete</button>` : ''}
      </td>
    </tr>`).join("") : `<tr><td colspan="7" class="empty">No patients match this view.</td></tr>`;

  if (allowDelete) {
    document.querySelectorAll('.row-delete').forEach(btn => btn.addEventListener('click', async (ev) => {
          ev.stopPropagation();
          const id = ev.target.dataset.id;
          const confirmed = await showConfirm('Delete this patient? This cannot be undone.');
          if (!confirmed) return;
          // delete from demo storage if used
          const demo = JSON.parse(localStorage.getItem('mf_demo_patients') || '[]');
          const remaining = demo.filter(p => String(p.id) !== String(id));
          localStorage.setItem('mf_demo_patients', JSON.stringify(remaining));
          // also remove from queue variable
          queue = queue.filter(p => String(p.id) !== String(id));
          renderQueue();
    }));
  }

  // Make rows clickable for admins (clicking row navigates to edit)
  if (isAdmin()) {
    document.querySelectorAll('#patientTableBody tr').forEach(tr => {
      tr.addEventListener('click', (ev) => {
        // ignore clicks on buttons/links
        if (ev.target.closest('button') || ev.target.closest('a')) return;
        const link = tr.querySelector('a.row-action');
        if (link) window.location.href = link.href;
      });
    });
  }
}

async function loadPatients() {
  refreshQueue.disabled = true;
  try {
    const response = await fetch("/api/patients");
    if (response.status === 401) { window.location.href = "login.html"; return; }
    if (!response.ok) throw new Error("Unable to load queue");
    const patients = await response.json();
    if (Array.isArray(patients) && patients.length) {
      queue = patients.map((patient, index) => ({ ...patient, hospitalNumber: patient.hospitalNumber || `Q-${String(index + 1).padStart(3, "0")}`, priority: Number(patient.priority || patient.esi || 3), arrival: patient.arrival || "--:--", wait: patient.wait || "Pending", status: patient.status || "Waiting" }));
      document.getElementById("patientsToday").textContent = patients.length;
      document.getElementById("waitingCount").textContent = patients.length;
      document.getElementById("urgentCount").textContent = queue.filter((patient) => patient.priority <= 2).length;
      message.textContent = "";
    }
  } catch (error) {
    // no backend: seed demo patients in localStorage if missing
    const existing = localStorage.getItem('mf_demo_patients');
    if (!existing) {
      localStorage.setItem('mf_demo_patients', JSON.stringify(demoQueue));
      queue = demoQueue.slice();
      document.getElementById("patientsToday").textContent = demoQueue.length;
      document.getElementById("waitingCount").textContent = demoQueue.length;
      document.getElementById("urgentCount").textContent = demoQueue.filter((p) => Number(p.priority) <= 2).length;
      message.textContent = "Demo queue seeded from repository data.";
      message.className = "message demo-message";
    } else {
      const demo = JSON.parse(existing || '[]');
      if (Array.isArray(demo)) {
        queue = demo;
        document.getElementById("patientsToday").textContent = demo.length;
        document.getElementById("waitingCount").textContent = demo.length;
        document.getElementById("urgentCount").textContent = demo.filter((p) => Number(p.priority) <= 2).length;
        message.textContent = "Showing demo queue from local storage.";
        message.className = "message demo-message";
      }
    }
  } finally {
    refreshQueue.disabled = false;
    renderQueue();
    applyUserPermissions();
  }
}

function applyUserPermissions() {
  const u = currentUser();
  const staffNameEl = document.querySelector('.staff-name');
  if (staffNameEl && u) {
    staffNameEl.innerHTML = `${u.displayName || u.username} <small>${u.role}</small>`;
  }
  // show register link only for doctors and admins
  if (registerLink) {
    registerLink.style.display = (isAdmin() || isDoctor()) ? '' : 'none';
  }
  if (userMgmtLink) {
    userMgmtLink.style.display = isAdmin() ? '' : 'none';
  }
}

searchInput.addEventListener("input", renderQueue);
priorityFilter.addEventListener("change", renderQueue);
refreshQueue.addEventListener("click", loadPatients);
logoutButton.addEventListener("click", async () => { await fetch("/api/logout", { method: "POST" }).catch(()=>{}); localStorage.removeItem('mf_current_user'); window.location.href = "login.html"; });

// initialize
renderQueue();
loadPatients();
