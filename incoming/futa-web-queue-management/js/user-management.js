const USERS_KEY = 'mf_demo_users';
const message = document.getElementById('message');
const usersList = document.getElementById('usersList');
const createUserForm = document.getElementById('createUserForm');

function ensureUsers() {
  const raw = localStorage.getItem(USERS_KEY);
  if (raw) return JSON.parse(raw);
  const base = [
    { username: 'admin', password: 'admin123', role: 'admin', displayName: 'Administrator' },
    { username: 'manager', password: 'manager123', role: 'admin', displayName: 'Operations Admin' },
    { username: 'doctor', password: 'doctor123', role: 'doctor', displayName: 'Dr. Demo' },
    { username: 'nurse', password: 'nurse123', role: 'nurse', displayName: 'Nurse Demo' }
  ];
  localStorage.setItem(USERS_KEY, JSON.stringify(base));
  return base;
}

function currentUser() { try { return JSON.parse(localStorage.getItem('mf_current_user')); } catch(e){return null;} }

function renderUsers() {
  const users = ensureUsers();
  usersList.innerHTML = users.map(u => `
    <div class="stat-card" style="display:flex;justify-content:space-between;align-items:center;">
      <div><strong>${u.displayName || u.username}</strong><div style="color:#6f7c89;font-size:12px">${u.username} · ${u.role}</div></div>
      <div>
        <button class="small-button" data-user="${u.username}">Edit</button>
        <button class="small-button danger" data-delete="${u.username}">Delete</button>
      </div>
    </div>
  `).join('');

  usersList.querySelectorAll('[data-delete]').forEach(btn => btn.addEventListener('click', (e) => {
    const name = e.target.dataset.delete;
    if (!confirm(`Remove user ${name}?`)) return;
    let users = ensureUsers();
    users = users.filter(u => u.username !== name);
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
    showMessage('User removed', 'success');
    renderUsers();
  }));

  usersList.querySelectorAll('[data-user]').forEach(btn => btn.addEventListener('click', (e) => {
    const name = e.target.dataset.user;
    const users = ensureUsers();
    const u = users.find(x => x.username === name);
    const newDisplay = prompt('Display name', u.displayName || u.username);
    if (newDisplay === null) return;
    u.displayName = newDisplay;
    localStorage.setItem(USERS_KEY, JSON.stringify(users));
    showMessage('User updated', 'success');
    renderUsers();
  }));
}

function showMessage(text, type) { message.textContent = text; message.className = `message ${type}`; }

createUserForm.addEventListener('submit', (e) => {
  e.preventDefault();
  const username = document.getElementById('newUsername').value.trim();
  const password = document.getElementById('newPassword').value;
  const displayName = document.getElementById('newDisplayName').value.trim();
  const role = document.getElementById('newRole').value;
  if (!username || !password) { showMessage('username and password required', 'error'); return; }
  const users = ensureUsers();
  if (users.find(u => u.username === username)) { showMessage('username exists', 'error'); return; }
  users.push({ username, password, displayName: displayName || username, role });
  localStorage.setItem(USERS_KEY, JSON.stringify(users));
  showMessage('User created', 'success');
  renderUsers();
  createUserForm.reset();
});

// guard: only admin allowed
const me = currentUser();
if (!me || me.role !== 'admin') {
  document.body.innerHTML = '<p style="padding:24px">Access denied. Admins only.</p>';
} else {
  document.querySelector('.staff-name').textContent = `${me.displayName || me.username} (${me.role})`;
  document.getElementById('logoutButton').addEventListener('click', () => { localStorage.removeItem('mf_current_user'); window.location.href = 'login.html'; });
  renderUsers();
}
