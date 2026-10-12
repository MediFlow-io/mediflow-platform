// Robust demo-capable login handler
(function(){
  const loginForm = document.getElementById('loginForm');
  let message = document.getElementById('message');
  if (!loginForm) return; // nothing on pages without login

  if (!message) {
    message = document.createElement('div');
    message.id = 'message';
    message.className = 'message';
    loginForm.prepend(message);
  }

  const DEMO_USERS_KEY = 'mf_demo_users';
  function ensureDemoUsers() {
    const raw = localStorage.getItem(DEMO_USERS_KEY);
    if (raw) {
      try { return JSON.parse(raw); } catch (e) { /* recreate below */ }
    }
    const users = [
      { username: 'admin', password: 'admin123', role: 'admin', displayName: 'Administrator' },
      { username: 'manager', password: 'manager123', role: 'admin', displayName: 'Operations Admin' },
      { username: 'doctor', password: 'doctor123', role: 'doctor', displayName: 'Dr. Demo' },
      { username: 'nurse', password: 'nurse123', role: 'nurse', displayName: 'Nurse Demo' }
    ];
    localStorage.setItem(DEMO_USERS_KEY, JSON.stringify(users));
    return users;
  }

  // case-insensitive username match
  function findLocalUser(username, password) {
    const users = ensureDemoUsers();
    const uname = String(username || '').trim().toLowerCase();
    return users.find(u => String(u.username || '').toLowerCase() === uname && u.password === password) || null;
  }

  function setCurrentUser(user) {
    if (!user) return;
    const safe = { username: user.username, role: user.role, displayName: user.displayName };
    localStorage.setItem('mf_current_user', JSON.stringify(safe));
  }

  async function attemptBackendLogin(staffId, password) {
    try {
      const resp = await fetch('/api/login', { method: 'POST', headers: { 'Content-Type':'application/json' }, body: JSON.stringify({ staffId, password }) });
      if (!resp.ok) return null;
      return await resp.json();
    } catch (e) { return null; }
  }

  loginForm.addEventListener('submit', async (ev) => {
    ev.preventDefault();
    const staffId = document.getElementById('staffId').value.trim();
    const password = document.getElementById('password').value;
    if (!staffId || !password) {
      message.textContent = 'Please enter username and password';
      message.className = 'message error';
      return;
    }

    message.textContent = 'Logging in...';
    message.className = 'message';

    const backend = await attemptBackendLogin(staffId, password);
    if (backend) {
      setCurrentUser({ username: staffId, role: backend.role || 'admin', displayName: backend.displayName || staffId });
      message.textContent = backend.message || 'Login successful';
      message.className = 'message success';
      return void setTimeout(() => window.location.href = 'dashboard.html', 300);
    }

    // fallback demo
    const local = findLocalUser(staffId, password);
    if (!local) {
      message.textContent = 'Invalid credentials';
      message.className = 'message error';
      return;
    }

    setCurrentUser(local);
    message.textContent = 'Signed in (demo)';
    message.className = 'message success';
    setTimeout(() => window.location.href = 'dashboard.html', 300);
  });

  // expose for debugging in page scope
  window._mf_debug = { ensureDemoUsers, findLocalUser };
  // ensure demo users exist immediately
  ensureDemoUsers();

  // wire demo-fill buttons to auto-fill the login form
  document.querySelectorAll('.demo-fill').forEach(btn => {
    btn.addEventListener('click', () => {
      const u = btn.dataset.username || '';
      const p = btn.dataset.password || '';
      const idEl = document.getElementById('staffId');
      const pwEl = document.getElementById('password');
      if (idEl) { idEl.value = u; idEl.dispatchEvent(new Event('input', { bubbles: true })); }
      if (pwEl) { pwEl.value = p; pwEl.dispatchEvent(new Event('input', { bubbles: true })); }
      // focus the login button so keyboard users can press Enter
      const submit = loginForm.querySelector('button[type=submit]') || loginForm.querySelector('button');
      if (submit) submit.focus();
    });
  });

})();
