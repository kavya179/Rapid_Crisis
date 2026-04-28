// ─── CrisisCore API Module ───────────────────────────────────────────────────
const API_BASE = 'http://localhost:5000/api';

const API = {
  async get(endpoint) {
    const res = await fetch(`${API_BASE}${endpoint}`);
    if (!res.ok) throw new Error(`GET ${endpoint} failed: ${res.status}`);
    return res.json();
  },
  async post(endpoint, data) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`POST ${endpoint} failed: ${res.status}`);
    return res.json();
  },
  async put(endpoint, data) {
    const res = await fetch(`${API_BASE}${endpoint}`, {
      method: 'PUT', headers: {'Content-Type':'application/json'},
      body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(`PUT ${endpoint} failed: ${res.status}`);
    return res.json();
  },
  incidents: {
    getAll: (status) => API.get('/incidents' + (status ? `?status=${status}` : '')),
    get: (id) => API.get(`/incidents/${id}`),
    create: (data) => API.post('/incidents', data),
    updateStatus: (id, status) => API.put(`/incidents/${id}/status`, {status}),
    addUpdate: (id, data) => API.post(`/incidents/${id}/update`, data),
    assign: (id, responder_id) => API.post(`/incidents/${id}/assign`, {responder_id}),
  },
  responders: {
    getAll: () => API.get('/responders'),
  },
  alerts: {
    getAll: () => API.get('/alerts'),
    markRead: () => API.put('/alerts/read', {}),
  },
  stats: () => API.get('/stats'),
  sos: (data) => API.post('/sos', data),
};

// ─── Utilities ───────────────────────────────────────────────────────────────
function timeAgo(dateStr) {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - date) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff/60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h ago`;
  return `${Math.floor(diff/86400)}d ago`;
}

function formatTime(dateStr) {
  return new Date(dateStr).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'});
}

function severityClass(sev) {
  return {'critical':'sev-critical','high':'sev-high','medium':'sev-medium','low':'sev-low'}[sev] || 'sev-low';
}

function typeIcon(type) {
  return {
    fire:'🔥', medical:'🚑', security:'🛡️', evacuation:'🚪',
    flood:'💧', power:'⚡', theft:'🔓', fight:'⚠️',
    emergency:'🆘', hazmat:'☢️', earthquake:'🌍', other:'📋'
  }[type] || '📋';
}

function showToast(msg, type='success') {
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `<span>${type==='success'?'✓':'✗'}</span> ${msg}`;
  document.body.appendChild(t);
  setTimeout(() => t.remove(), 3000);
}

function statusClass(status) {
  return {'active':'st-active','investigating':'st-investigating','resolved':'st-resolved','contained':'st-contained'}[status] || 'st-active';
}

// Live clock
function updateClock() {
  const el = document.getElementById('liveTime');
  if (el) el.textContent = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}
setInterval(updateClock, 1000);
updateClock();

// Alert bell
let alertsOpen = false;
function toggleAlerts() {
  const dd = document.getElementById('alertDropdown');
  if (!dd) return;
  alertsOpen = !alertsOpen;
  dd.classList.toggle('hidden', !alertsOpen);
  if (alertsOpen) loadAlerts();
}

async function loadAlerts() {
  const list = document.getElementById('alertList');
  if (!list) return;
  try {
    const alerts = await API.alerts.getAll();
    const badge = document.getElementById('alertCount');
    const unread = alerts.filter(a => !a.is_read).length;
    if (badge) badge.textContent = unread;
    list.innerHTML = alerts.length === 0
      ? '<div class="alert-item" style="color:var(--text-dim);text-align:center;">No alerts</div>'
      : alerts.map(a => `
          <div class="alert-item ${!a.is_read?'unread':''}">
            <div>${a.message}</div>
            <div class="alert-time">${timeAgo(a.created_at)}</div>
          </div>`).join('');
  } catch (e) {}
}

async function markAllRead() {
  await API.alerts.markRead();
  const badge = document.getElementById('alertCount');
  if (badge) badge.textContent = '0';
  await loadAlerts();
}

function dismissAlert() {
  const banner = document.getElementById('alertBanner');
  if (banner) banner.classList.add('hidden');
}

// Close dropdown on outside click
document.addEventListener('click', e => {
  const dd = document.getElementById('alertDropdown');
  const bell = document.querySelector('.alert-bell');
  if (dd && bell && !dd.contains(e.target) && !bell.contains(e.target)) {
    dd.classList.add('hidden');
    alertsOpen = false;
  }
});

// Initial alert badge load
(async () => {
  try {
    const alerts = await API.alerts.getAll();
    const badge = document.getElementById('alertCount');
    const unread = alerts.filter(a => !a.is_read).length;
    if (badge) badge.textContent = unread;
    // Show critical alert banner
    const critical = alerts.find(a => !a.is_read && a.alert_type === 'critical');
    if (critical) {
      const banner = document.getElementById('alertBanner');
      const text = document.getElementById('alertText');
      if (banner && text) { text.textContent = critical.message; banner.classList.remove('hidden'); }
    }
  } catch(e) {}
})();