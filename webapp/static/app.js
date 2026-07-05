const tg = window.Telegram && window.Telegram.WebApp;
const qs = new URLSearchParams(location.search);
const devTgId = qs.get('tg_id');
const initData = (tg && tg.initData) || '';

const appEl = document.getElementById('app');
const modalOverlay = document.getElementById('modal-overlay');
const modalCard = document.getElementById('modal-card');
const toastEl = document.getElementById('toast');

let ADMIN_TAB = 'home';
let EMP_TAB = 'home';

function applyTheme() {
  if (!tg) return;
  const tp = tg.themeParams || {};
  const root = document.documentElement.style;
  // Fon/matn ranglari Telegram mavzusiga (light/dark) moslashadi,
  // lekin brend aksent rangi (yashil) har doim o'zgarmas qoladi.
  const map = {
    bg_color: '--tg-bg',
    text_color: '--tg-text',
    hint_color: '--tg-hint',
    secondary_bg_color: '--tg-secondary-bg',
  };
  Object.entries(map).forEach(([k, v]) => {
    if (tp[k]) root.setProperty(v, tp[k]);
  });
}

function applyAutoNightMode() {
  const hour = new Date().getHours();
  const isNight = hour >= 20 || hour < 7;
  const root = document.documentElement.style;
  if (isNight) {
    root.setProperty('--tg-bg', '#0f1115');
    root.setProperty('--tg-text', '#f2f2f2');
    root.setProperty('--tg-hint', '#9a9da3');
    root.setProperty('--tg-secondary-bg', '#1c1e24');
    document.body.classList.add('night-mode');
  } else {
    document.body.classList.remove('night-mode');
  }
}

function toast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.remove('hidden');
  setTimeout(() => toastEl.classList.add('hidden'), 2500);
}

function openModal(html) {
  modalCard.innerHTML = html;
  modalOverlay.classList.remove('hidden');
}

function closeModal() {
  modalOverlay.classList.add('hidden');
  modalCard.innerHTML = '';
}

modalOverlay.addEventListener('click', (e) => {
  if (e.target === modalOverlay) closeModal();
});

async function api(path, options = {}) {
  const headers = Object.assign({ 'Content-Type': 'application/json' }, options.headers || {});
  if (initData) {
    headers['X-Init-Data'] = initData;
  } else if (devTgId) {
    headers['X-Dev-Tg-Id'] = devTgId;
  }
  const res = await fetch(path, Object.assign({}, options, { headers }));
  let body = null;
  try { body = await res.json(); } catch (e) { body = null; }
  if (!res.ok) {
    throw new Error((body && body.detail) || "Xatolik yuz berdi");
  }
  return body;
}

function money(n) {
  n = n || 0;
  return Math.round(n).toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ') + " so'm";
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str || '';
  return div.innerHTML;
}

// ---------- Bootstrap ----------

async function init() {
  if (tg) {
    tg.ready();
    tg.expand();
    applyTheme();
  }
  applyAutoNightMode();
  setInterval(applyAutoNightMode, 10 * 60 * 1000);
  if (!initData && !devTgId) {
    renderCenter('🔒', 'Avtorizatsiya topilmadi', 'Iltimos, ilovani Telegram bot orqali oching.');
    return;
  }
  try {
    const profile = await api('/api/profile');
    route(profile);
  } catch (e) {
    renderCenter('⚠️', 'Xatolik', e.message);
  }
}

function route(profile) {
  if (profile.role === 'admin') return renderAdminShell();
  if (profile.role === 'employee') return renderEmployeeShell(profile.employee);
  if (profile.role === 'pending') {
    return renderCenter('⏳', "So'rovingiz ko'rib chiqilmoqda", "HR admin tez orada javob beradi.");
  }
  return renderRegisterForm(profile.role === 'rejected');
}

function renderCenter(emoji, title, subtitle) {
  appEl.innerHTML = `
    <div class="center-screen">
      <div class="emoji">${emoji}</div>
      <div class="card-title">${title}</div>
      <div style="color:var(--tg-hint);font-size:14px;">${subtitle || ''}</div>
    </div>`;
}

// ---------- Registration ----------

function renderRegisterForm(wasRejected) {
  appEl.innerHTML = `
    <div class="header">
      <div class="greeting">👋 Xush kelibsiz</div>
      <div class="subtitle">${wasRejected ? "Avvalgi so'rovingiz rad etilgan edi. Qaytadan yuboring." : 'Ishga chiqish uchun ro\'yxatdan o\'ting'}</div>
    </div>
    <div class="content">
      <div class="card">
        <div class="field">
          <label class="field-label">To'liq ism-familiya</label>
          <input id="reg-name" type="text" placeholder="Ali Valiyev" />
        </div>
        <div class="field">
          <label class="field-label">Telefon raqam</label>
          <input id="reg-phone" type="tel" placeholder="+998901234567" />
        </div>
        <button class="btn" id="reg-submit">✅ Yuborish</button>
      </div>
    </div>`;

  document.getElementById('reg-submit').addEventListener('click', async () => {
    const full_name = document.getElementById('reg-name').value.trim();
    const phone = document.getElementById('reg-phone').value.trim();
    if (!full_name || !phone) return toast("Iltimos, barcha maydonlarni to'ldiring");
    try {
      await api('/api/register', { method: 'POST', body: JSON.stringify({ full_name, phone }) });
      renderCenter('✅', "So'rov yuborildi", 'HR admin ko\'rib chiqib, sizga xabar beradi.');
    } catch (e) {
      toast(e.message);
    }
  });
}

// ================= EMPLOYEE =================

async function renderEmployeeShell(employee) {
  appEl.innerHTML = `<div id="emp-content"></div>` + tabbarHtml('employee');
  bindTabbar('employee');
  await renderEmployeeTab(employee);
}

function tabbarHtml(role) {
  const empTabs = [
    ['home', '🏠', 'Bosh sahifa'],
    ['leave', '🌴', "Ta'til"],
    ['tasks', '📋', 'Vazifalar'],
    ['salary', '💰', 'Maosh'],
    ['profile', '👤', 'Profil'],
  ];
  const adminTabs = [
    ['home', '🏠', 'Bosh sahifa'],
    ['employees', '👥', 'Xodimlar'],
    ['attendance', '📅', 'Davomat'],
    ['pending', '🆕', "So'rovlar"],
    ['leaves', '🌴', "Ta'til"],
    ['tasks', '📋', 'Vazifalar'],
  ];
  const tabs = role === 'employee' ? empTabs : adminTabs;
  const active = role === 'employee' ? EMP_TAB : ADMIN_TAB;
  return `<div class="tabbar">${tabs.map(([id, icon, label]) => `
    <button class="tab-item ${active === id ? 'active' : ''}" data-tab="${id}">
      <span class="icon">${icon}</span><span>${label}</span>
    </button>`).join('')}</div>`;
}

function bindTabbar(role) {
  document.querySelectorAll('.tab-item').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (role === 'employee') {
        EMP_TAB = btn.dataset.tab;
        const employee = await api('/api/profile');
        await renderEmployeeShell(employee.employee);
      } else {
        ADMIN_TAB = btn.dataset.tab;
        await renderAdminShell();
      }
    });
  });
}

async function renderEmployeeTab(employee) {
  const container = document.getElementById('emp-content');
  if (EMP_TAB === 'home') return renderEmpHome(container, employee);
  if (EMP_TAB === 'leave') return renderEmpLeave(container, employee);
  if (EMP_TAB === 'tasks') return renderEmpTasks(container, employee);
  if (EMP_TAB === 'salary') return renderEmpSalary(container, employee);
  if (EMP_TAB === 'profile') return renderEmpProfile(container, employee);
}

async function renderEmpHome(container, employee) {
  const today = await api('/api/attendance/today');
  const t = (v) => (v ? v.slice(11, 16) : '--:--');

  const canCheckin = !today.check_in;
  const canLunchOut = !!today.check_in && !today.lunch_out && !today.check_out;
  const canLunchIn = !!today.lunch_out && !today.lunch_in && !today.check_out;
  const canCheckout = !!today.check_in && !today.check_out;

  container.innerHTML = `
    <div class="header-gradient">
      <div class="greeting">👋 Salom, ${escapeHtml(employee.full_name.split(' ')[0])}!</div>
      <div class="subtitle" style="color:rgba(255,255,255,0.85);">${employee.position || ''} · ${employee.department || ''}</div>
    </div>
    <div class="content" style="margin-top:-28px;">
      <div class="card">
        <div class="card-title">Bugungi davomat</div>
        <div class="attendance-status four">
          <div class="box">
            <div class="time">${t(today.check_in)}</div>
            <div class="label">Keldim</div>
          </div>
          <div class="box">
            <div class="time">${t(today.lunch_out)}</div>
            <div class="label">Tushlikka</div>
          </div>
          <div class="box">
            <div class="time">${t(today.lunch_in)}</div>
            <div class="label">Tushlikdan</div>
          </div>
          <div class="box">
            <div class="time">${t(today.check_out)}</div>
            <div class="label">Ketdim</div>
          </div>
        </div>
      </div>
      <div class="btn-row">
        <button class="btn" id="btn-checkin" ${canCheckin ? '' : 'disabled'}>✅ Keldim</button>
        <button class="btn secondary" id="btn-lunchout" ${canLunchOut ? '' : 'disabled'}>🍽 Tushlikka chiqdim</button>
      </div>
      <div class="btn-row">
        <button class="btn secondary" id="btn-lunchin" ${canLunchIn ? '' : 'disabled'}>🍽 Tushlikdan keldim</button>
        <button class="btn danger" id="btn-checkout" ${canCheckout ? '' : 'disabled'}>🚪 Ketdim</button>
      </div>
    </div>`;

  const bind = (id, endpoint, okMsg) => {
    document.getElementById(id).addEventListener('click', async () => {
      try {
        const r = await api(endpoint, { method: 'POST' });
        toast(r.ok ? okMsg : 'Amalga oshmadi');
        renderEmpHome(container, employee);
      } catch (e) { toast(e.message); }
    });
  };

  bind('btn-checkin', '/api/attendance/checkin', '✅ Kelganingiz qayd etildi');
  bind('btn-lunchout', '/api/attendance/lunch-out', '🍽 Tushlikka chiqishingiz qayd etildi');
  bind('btn-lunchin', '/api/attendance/lunch-in', '🍽 Tushlikdan qaytishingiz qayd etildi');
  bind('btn-checkout', '/api/attendance/checkout', '🚪 Ketganingiz qayd etildi');
}

async function renderEmpLeave(container, employee) {
  const history = await api('/api/leave/history');
  const icons = { pending: '⏳', approved: '✅', rejected: '❌' };
  container.innerHTML = `
    <div class="header">
      <div class="greeting">🌴 Ta'til so'rovlari</div>
    </div>
    <div class="content">
      <button class="btn" id="new-leave">+ Yangi so'rov</button>
      ${history.length === 0 ? '<div class="empty-state">Hali so\'rovlar yo\'q</div>' : history.map((r) => `
        <div class="card">
          <div class="card-row"><span class="label">Tur</span><span>${escapeHtml(r.leave_type)}</span></div>
          <div class="card-row"><span class="label">Sana</span><span>${r.start_date} — ${r.end_date}</span></div>
          <div class="card-row"><span class="label">Holat</span><span class="pill ${r.status}">${icons[r.status] || ''} ${r.status}</span></div>
        </div>`).join('')}
    </div>`;

  document.getElementById('new-leave').addEventListener('click', () => {
    openModal(`
      <h3>Yangi ta'til so'rovi</h3>
      <div class="field">
        <label class="field-label">Turi</label>
        <select id="lv-type">
          <option>Ta'til</option>
          <option>Bemorlik</option>
          <option>Boshqa</option>
        </select>
      </div>
      <div class="field">
        <label class="field-label">Boshlanish sanasi</label>
        <input id="lv-start" type="date" />
      </div>
      <div class="field">
        <label class="field-label">Tugash sanasi</label>
        <input id="lv-end" type="date" />
      </div>
      <div class="field">
        <label class="field-label">Sabab</label>
        <textarea id="lv-reason" placeholder="Qisqacha sabab"></textarea>
      </div>
      <button class="btn" id="lv-submit">Yuborish</button>`);

    document.getElementById('lv-submit').addEventListener('click', async () => {
      const leave_type = document.getElementById('lv-type').value;
      const start_date = document.getElementById('lv-start').value;
      const end_date = document.getElementById('lv-end').value;
      const reason = document.getElementById('lv-reason').value.trim();
      if (!start_date || !end_date) return toast('Sanalarni kiriting');
      try {
        await api('/api/leave', { method: 'POST', body: JSON.stringify({ leave_type, start_date, end_date, reason }) });
        closeModal();
        toast("✅ So'rov yuborildi");
        renderEmpLeave(container, employee);
      } catch (e) { toast(e.message); }
    });
  });
}

async function renderEmpTasks(container, employee) {
  const tasks = await api('/api/tasks');
  container.innerHTML = `
    <div class="header"><div class="greeting">📋 Mening vazifalarim</div></div>
    <div class="content">
      ${tasks.length === 0 ? '<div class="empty-state">Hozircha vazifa yo\'q</div>' : tasks.map((t) => `
        <div class="card">
          <div class="card-title">${escapeHtml(t.title)}</div>
          <div style="font-size:13px;color:var(--tg-hint);margin-bottom:8px;">${escapeHtml(t.description || '')}</div>
          <div class="card-row"><span class="label">Muddat</span><span>${t.deadline || '-'}</span></div>
          <div class="card-row"><span class="label">Holat</span><span class="pill ${t.status}">${t.status === 'done' ? '✅ Bajarilgan' : '🕒 Yangi'}</span></div>
          ${t.status === 'new' ? `<button class="btn small" style="margin-top:8px;" data-task="${t.id}">✅ Bajarildi</button>` : ''}
        </div>`).join('')}
    </div>`;

  container.querySelectorAll('[data-task]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      try {
        await api(`/api/tasks/${btn.dataset.task}/done`, { method: 'POST' });
        toast('✅ Rahmat!');
        renderEmpTasks(container, employee);
      } catch (e) { toast(e.message); }
    });
  });
}

function renderEmpSalary(container, employee) {
  container.innerHTML = `
    <div class="header"><div class="greeting">💰 Mening maoshim</div></div>
    <div class="content">
      <div class="card">
        <div class="card-title">Oylik maosh</div>
        <div style="font-size:26px;font-weight:700;margin-top:6px;">${money(employee.salary)}</div>
      </div>
    </div>`;
}

function renderEmpProfile(container, employee) {
  container.innerHTML = `
    <div class="header"><div class="greeting">👤 Profilim</div></div>
    <div class="content">
      <div class="card">
        <div class="card-row"><span class="label">Ism</span><span>${escapeHtml(employee.full_name)}</span></div>
        <div class="card-row"><span class="label">Lavozim</span><span>${escapeHtml(employee.position || '-')}</span></div>
        <div class="card-row"><span class="label">Bo'lim</span><span>${escapeHtml(employee.department || '-')}</span></div>
        <div class="card-row"><span class="label">Telefon</span><span>${escapeHtml(employee.phone || '-')}</span></div>
        <div class="card-row"><span class="label">Ishga qabul</span><span>${(employee.created_at || '').slice(0, 10)}</span></div>
      </div>
    </div>`;
}

// ================= ADMIN =================

async function renderAdminShell() {
  appEl.innerHTML = `<div id="admin-content"></div>` + tabbarHtml('admin');
  bindTabbar('admin');
  const container = document.getElementById('admin-content');
  if (ADMIN_TAB === 'home') return renderAdminHome(container);
  if (ADMIN_TAB === 'employees') return renderAdminEmployees(container);
  if (ADMIN_TAB === 'attendance') return renderAdminAttendance(container);
  if (ADMIN_TAB === 'pending') return renderAdminPending(container);
  if (ADMIN_TAB === 'leaves') return renderAdminLeaves(container);
  if (ADMIN_TAB === 'tasks') return renderAdminTasks(container);
}

function attendanceStatusInfo(row) {
  if (!row.check_in) return { icon: '❌', label: 'Kelmadi', cls: 'rejected' };
  if (row.check_out) return { icon: '🚪', label: 'Ketdi', cls: 'done' };
  if (row.lunch_out && !row.lunch_in) return { icon: '🍽', label: 'Tushlikda', cls: 'pending' };
  return { icon: '🟢', label: 'Ishda', cls: 'new' };
}

async function renderAdminAttendance(container) {
  const rows = await api('/api/admin/attendance');
  const t = (v) => (v ? v.slice(11, 16) : '--:--');

  container.innerHTML = `
    <div class="header"><div class="greeting">📅 Bugungi davomat</div><div class="subtitle">${rows.length} ta xodim</div></div>
    <div class="content">
      ${rows.length === 0 ? '<div class="empty-state">Hozircha xodim yo\'q</div>' : rows.map((r) => {
        const s = attendanceStatusInfo(r);
        return `
        <div class="card">
          <div class="employee-row" style="margin-bottom:10px;">
            ${avatarHtml(r.full_name)}
            <div style="flex:1;">
              <div class="card-title">${escapeHtml(r.full_name)}</div>
              <div style="font-size:12px;color:var(--tg-hint);">${escapeHtml(r.department || '-')}</div>
            </div>
            <div class="pill ${s.cls}">${s.icon} ${s.label}</div>
          </div>
          <div class="attendance-status four">
            <div class="box"><div class="time">${t(r.check_in)}</div><div class="label">Keldi</div></div>
            <div class="box"><div class="time">${t(r.lunch_out)}</div><div class="label">Tushlikka</div></div>
            <div class="box"><div class="time">${t(r.lunch_in)}</div><div class="label">Tushlikdan</div></div>
            <div class="box"><div class="time">${t(r.check_out)}</div><div class="label">Ketdi</div></div>
          </div>
        </div>`;
      }).join('')}
    </div>`;
}

const AVATAR_PALETTE = ['#22c55e', '#15803d', '#4ade80', '#0d9488', '#65a30d', '#059669'];

function initials(name) {
  return (name || '?').trim().split(/\s+/).slice(0, 2).map((p) => p[0]).join('').toUpperCase();
}

function avatarColor(name) {
  let hash = 0;
  for (const ch of (name || '')) hash = (hash * 31 + ch.charCodeAt(0)) % AVATAR_PALETTE.length;
  return AVATAR_PALETTE[Math.abs(hash) % AVATAR_PALETTE.length];
}

function avatarHtml(name) {
  return `<div class="avatar" style="background:${avatarColor(name)}">${initials(name)}</div>`;
}

function timeAgo(dateStr) {
  if (!dateStr) return '';
  const then = new Date(dateStr.replace(' ', 'T'));
  const diffMin = Math.floor((Date.now() - then.getTime()) / 60000);
  if (diffMin < 1) return 'hozirgina';
  if (diffMin < 60) return `${diffMin} daqiqa oldin`;
  const diffHour = Math.floor(diffMin / 60);
  if (diffHour < 24) return `${diffHour} soat oldin`;
  return `${Math.floor(diffHour / 24)} kun oldin`;
}

async function renderAdminHome(container) {
  const [s, activity] = await Promise.all([
    api('/api/admin/stats'),
    api('/api/admin/activity'),
  ]);
  container.innerHTML = `
    <div class="header-gradient">
      <div class="greeting">🏠 Boshqaruv paneli</div>
      <div class="subtitle" style="color:rgba(255,255,255,0.85);">Kompaniyangizdagi barcha jarayonlar bir joyda</div>
    </div>
    <div class="content" style="margin-top:-28px;">
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-icon">👥</div><div class="stat-num">${s.total_employees}</div><div class="stat-label">Jami xodimlar</div></div>
        <div class="stat-card"><div class="stat-icon">🟢</div><div class="stat-num">${s.present_today}</div><div class="stat-label">Bugun kelganlar</div></div>
        <div class="stat-card"><div class="stat-icon">🆕</div><div class="stat-num">${s.pending_registrations}</div><div class="stat-label">Yangi so'rovlar</div></div>
        <div class="stat-card"><div class="stat-icon">📋</div><div class="stat-num">${s.tasks_done}/${s.tasks_total}</div><div class="stat-label">Vazifalar</div></div>
      </div>
      <div class="btn-row">
        <button class="btn" id="qa-add-employee">➕ Xodim qo'shish</button>
        <button class="btn secondary" id="qa-announcement">📢 E'lon</button>
      </div>
      <div class="card">
        <div class="card-title">🕒 So'nggi faoliyat</div>
        <div class="activity-list">
          ${activity.length === 0 ? '<div class="empty-state">Hozircha faoliyat yo\'q</div>' : activity.map((a) => `
            <div class="activity-item">
              <div class="activity-icon">${a.icon}</div>
              <div class="activity-body">
                <div class="activity-text">${escapeHtml(a.text)}</div>
                <div class="activity-time">${timeAgo(a.created_at)}</div>
              </div>
            </div>`).join('')}
        </div>
      </div>
    </div>`;

  document.getElementById('qa-add-employee').addEventListener('click', () => openAddEmployeeModal(container, renderAdminHome));
  document.getElementById('qa-announcement').addEventListener('click', () => openAnnouncementModal());
}

function openAnnouncementModal() {
  openModal(`
    <h3>📢 E'lon yuborish</h3>
    <div class="field">
      <label class="field-label">Matn</label>
      <textarea id="ann-text" placeholder="E'lon matnini kiriting"></textarea>
    </div>
    <button class="btn" id="ann-submit">Yuborish</button>`);

  document.getElementById('ann-submit').addEventListener('click', async () => {
    const text = document.getElementById('ann-text').value.trim();
    if (!text) return toast('Matnni kiriting');
    try {
      const r = await api('/api/admin/announcement', { method: 'POST', body: JSON.stringify({ text }) });
      closeModal();
      toast(`✅ ${r.sent}/${r.total} xodimga yuborildi`);
    } catch (e) { toast(e.message); }
  });
}

function openAddEmployeeModal(container, refreshFn) {
  openModal(`
    <h3>➕ Yangi xodim qo'shish</h3>
    <div class="field">
      <label class="field-label">Telegram ID</label>
      <input id="ae-tgid" type="number" placeholder="123456789" />
    </div>
    <div class="field">
      <label class="field-label">To'liq ism-familiya</label>
      <input id="ae-name" type="text" placeholder="Ali Valiyev" />
    </div>
    <div class="field">
      <label class="field-label">Telefon</label>
      <input id="ae-phone" type="tel" placeholder="+998901234567" />
    </div>
    <div class="field">
      <label class="field-label">Lavozim</label>
      <input id="ae-position" type="text" placeholder="Dasturchi" />
    </div>
    <div class="field">
      <label class="field-label">Bo'lim</label>
      <input id="ae-department" type="text" placeholder="IT bo'limi" />
    </div>
    <div class="field">
      <label class="field-label">Oylik maosh (so'm)</label>
      <input id="ae-salary" type="number" placeholder="5000000" />
    </div>
    <div style="font-size:12px;color:var(--tg-hint);margin-bottom:12px;">
      ℹ️ Xodim Telegram ID'sini bilish uchun u <a href="https://t.me/userinfobot" target="_blank">@userinfobot</a>ga yozishi kerak. Bildirishnoma olishi uchun avval botga /start bosgan bo'lishi kerak.
    </div>
    <button class="btn" id="ae-submit">Qo'shish</button>`);

  document.getElementById('ae-submit').addEventListener('click', async () => {
    const telegram_id = parseInt(document.getElementById('ae-tgid').value);
    const full_name = document.getElementById('ae-name').value.trim();
    const phone = document.getElementById('ae-phone').value.trim();
    const position = document.getElementById('ae-position').value.trim();
    const department = document.getElementById('ae-department').value.trim();
    const salary = parseFloat(document.getElementById('ae-salary').value) || 0;
    if (!telegram_id || !full_name || !position || !department) {
      return toast("Barcha majburiy maydonlarni to'ldiring");
    }
    try {
      const r = await api('/api/admin/employees', {
        method: 'POST',
        body: JSON.stringify({ telegram_id, full_name, phone, position, department, salary }),
      });
      closeModal();
      toast(r.notified ? '✅ Xodim qo\'shildi va xabardor qilindi' : "✅ Xodim qo'shildi (bildirishnoma yuborilmadi — u botga /start bosmagan)");
      refreshFn(container);
    } catch (e) { toast(e.message); }
  });
}

function employeeListHtml(employees) {
  if (employees.length === 0) return '<div class="empty-state">Hech kim topilmadi</div>';
  return employees.map((e) => `
    <div class="card">
      <div class="employee-row">
        ${avatarHtml(e.full_name)}
        <div>
          <div class="card-title">${escapeHtml(e.full_name)}</div>
          <div style="font-size:12px;color:var(--tg-hint);">${escapeHtml(e.position || '-')} · ${escapeHtml(e.department || '-')}</div>
        </div>
      </div>
      <div class="card-row"><span class="label">Maosh</span><span>${money(e.salary)}</span></div>
      <div class="btn-row" style="margin-top:8px;">
        <button class="btn small secondary" data-salary="${e.id}">💰 Maosh</button>
        <button class="btn small danger" data-delete="${e.id}">🗑 O'chirish</button>
      </div>
    </div>`).join('');
}

function bindEmployeeListActions(container) {
  container.querySelectorAll('[data-salary]').forEach((btn) => {
    btn.addEventListener('click', () => openSalaryModal(btn.dataset.salary, container));
  });
  container.querySelectorAll('[data-delete]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      if (!confirm("Xodimni o'chirmoqchimisiz?")) return;
      await api(`/api/admin/employees/${btn.dataset.delete}`, { method: 'DELETE' });
      toast("O'chirildi");
      renderAdminEmployees(container);
    });
  });
}

async function renderAdminEmployees(container) {
  const employees = await api('/api/admin/employees');
  container.innerHTML = `
    <div class="header"><div class="greeting">👥 Xodimlar</div><div class="subtitle">${employees.length} ta tasdiqlangan xodim</div></div>
    <div class="content">
      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input id="employee-search" type="text" placeholder="Ism, lavozim yoki bo'lim bo'yicha qidiring..." />
      </div>
      <button class="btn" id="add-employee-btn">➕ Xodim qo'shish</button>
      <div id="employee-list">${employeeListHtml(employees)}</div>
    </div>`;

  document.getElementById('add-employee-btn').addEventListener('click', () => openAddEmployeeModal(container, renderAdminEmployees));
  bindEmployeeListActions(container);

  document.getElementById('employee-search').addEventListener('input', (e) => {
    const q = e.target.value.trim().toLowerCase();
    const filtered = !q ? employees : employees.filter((emp) =>
      [emp.full_name, emp.position, emp.department].some((f) => (f || '').toLowerCase().includes(q))
    );
    const listEl = document.getElementById('employee-list');
    listEl.innerHTML = employeeListHtml(filtered);
    bindEmployeeListActions(container);
  });
}

function openSalaryModal(employeeId, container) {
  openModal(`
    <h3>💰 Maosh belgilash</h3>
    <div class="field">
      <label class="field-label">Yangi oylik maosh (so'm)</label>
      <input id="salary-amount" type="number" placeholder="5000000" />
    </div>
    <button class="btn" id="salary-submit">Saqlash</button>`);

  document.getElementById('salary-submit').addEventListener('click', async () => {
    const amount = parseFloat(document.getElementById('salary-amount').value);
    if (!amount) return toast("To'g'ri son kiriting");
    try {
      await api('/api/admin/salary', { method: 'POST', body: JSON.stringify({ employee_id: parseInt(employeeId), amount }) });
      closeModal();
      toast('✅ Maosh yangilandi');
      renderAdminEmployees(container);
    } catch (e) { toast(e.message); }
  });
}

async function renderAdminPending(container) {
  const pending = await api('/api/admin/pending');
  container.innerHTML = `
    <div class="header"><div class="greeting">🆕 Yangi so'rovlar</div></div>
    <div class="content">
      ${pending.length === 0 ? '<div class="empty-state">Yangi so\'rovlar yo\'q</div>' : pending.map((e) => `
        <div class="card">
          <div class="card-title">${escapeHtml(e.full_name)}</div>
          <div class="card-row"><span class="label">Telefon</span><span>${escapeHtml(e.phone || '-')}</span></div>
          <div class="btn-row" style="margin-top:8px;">
            <button class="btn small" data-approve="${e.id}">✅ Tasdiqlash</button>
            <button class="btn small danger" data-reject="${e.id}">❌ Rad etish</button>
          </div>
        </div>`).join('')}
    </div>`;

  container.querySelectorAll('[data-approve]').forEach((btn) => {
    btn.addEventListener('click', () => openApproveModal(btn.dataset.approve, container));
  });
  container.querySelectorAll('[data-reject]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/api/admin/employees/${btn.dataset.reject}/reject`, { method: 'POST' });
      toast('Rad etildi');
      renderAdminPending(container);
    });
  });
}

function openApproveModal(employeeId, container) {
  openModal(`
    <h3>✅ Xodimni tasdiqlash</h3>
    <div class="field">
      <label class="field-label">Lavozim</label>
      <input id="ap-position" type="text" placeholder="Dasturchi" />
    </div>
    <div class="field">
      <label class="field-label">Bo'lim</label>
      <input id="ap-department" type="text" placeholder="IT bo'limi" />
    </div>
    <div class="field">
      <label class="field-label">Oylik maosh (so'm)</label>
      <input id="ap-salary" type="number" placeholder="5000000" />
    </div>
    <button class="btn" id="ap-submit">Tasdiqlash</button>`);

  document.getElementById('ap-submit').addEventListener('click', async () => {
    const position = document.getElementById('ap-position').value.trim();
    const department = document.getElementById('ap-department').value.trim();
    const salary = parseFloat(document.getElementById('ap-salary').value) || 0;
    if (!position || !department) return toast("Barcha maydonlarni to'ldiring");
    try {
      await api(`/api/admin/employees/${employeeId}/approve`, {
        method: 'POST',
        body: JSON.stringify({ position, department, salary }),
      });
      closeModal();
      toast('✅ Tasdiqlandi');
      renderAdminPending(container);
    } catch (e) { toast(e.message); }
  });
}

function kanbanHtml(columns) {
  return `<div class="kanban">${columns.map((col) => `
    <div class="kanban-column">
      <div class="kanban-header ${col.key}">
        <span>${col.label}</span>
        <span class="count">${col.items.length}</span>
      </div>
      ${col.items.length === 0 ? '<div class="kanban-empty">Bo\'sh</div>' : col.items.join('')}
    </div>`).join('')}</div>`;
}

function leaveCardHtml(l) {
  const icons = { pending: '⏳', approved: '✅', rejected: '❌' };
  return `
    <div class="card">
      <div class="card-title">${escapeHtml(l.full_name)}</div>
      <div class="card-row"><span class="label">Tur</span><span>${escapeHtml(l.leave_type)}</span></div>
      <div class="card-row"><span class="label">Sana</span><span>${l.start_date} — ${l.end_date}</span></div>
      <div class="card-row"><span class="label">Sabab</span><span>${escapeHtml(l.reason || '-')}</span></div>
      ${l.status === 'pending' ? `
      <div class="btn-row" style="margin-top:8px;">
        <button class="btn small" data-lapprove="${l.id}">✅ Tasdiqlash</button>
        <button class="btn small danger" data-lreject="${l.id}">❌ Rad etish</button>
      </div>` : `<div class="pill ${l.status}" style="margin-top:6px;">${icons[l.status]} ${l.status}</div>`}
    </div>`;
}

function bindLeaveActions(container) {
  container.querySelectorAll('[data-lapprove]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/api/admin/leaves/${btn.dataset.lapprove}/approve`, { method: 'POST' });
      toast('✅ Tasdiqlandi');
      renderAdminLeaves(container);
    });
  });
  container.querySelectorAll('[data-lreject]').forEach((btn) => {
    btn.addEventListener('click', async () => {
      await api(`/api/admin/leaves/${btn.dataset.lreject}/reject`, { method: 'POST' });
      toast('Rad etildi');
      renderAdminLeaves(container);
    });
  });
}

async function renderAdminLeaves(container) {
  const leaves = await api('/api/admin/leaves');
  const byStatus = (s) => leaves.filter((l) => l.status === s).map(leaveCardHtml);

  container.innerHTML = `
    <div class="header"><div class="greeting">🌴 Ta'til so'rovlari</div></div>
    <div class="content">
      ${kanbanHtml([
        { key: 'pending', label: '⏳ KUTILAYOTGAN', items: byStatus('pending') },
        { key: 'approved', label: '✅ TASDIQLANGAN', items: byStatus('approved') },
        { key: 'rejected', label: '❌ RAD ETILGAN', items: byStatus('rejected') },
      ])}
    </div>`;

  bindLeaveActions(container);
}

function taskCardHtml(t) {
  return `
    <div class="card">
      <div class="card-title">${escapeHtml(t.title)}</div>
      <div class="card-row"><span class="label">Xodim</span><span>${escapeHtml(t.full_name)}</span></div>
      <div class="card-row"><span class="label">Muddat</span><span>${t.deadline || '-'}</span></div>
    </div>`;
}

async function renderAdminTasks(container) {
  const [tasks, employees] = await Promise.all([
    api('/api/admin/tasks'),
    api('/api/admin/employees'),
  ]);
  const newTasks = tasks.filter((t) => t.status !== 'done').map(taskCardHtml);
  const doneTasks = tasks.filter((t) => t.status === 'done').map(taskCardHtml);

  container.innerHTML = `
    <div class="header"><div class="greeting">📋 Vazifalar</div></div>
    <div class="content">
      <button class="btn" id="new-task">+ Yangi vazifa</button>
      ${kanbanHtml([
        { key: 'new', label: '🕒 YANGI', items: newTasks },
        { key: 'done', label: '✅ BAJARILGAN', items: doneTasks },
      ])}
    </div>`;

  document.getElementById('new-task').addEventListener('click', () => {
    openModal(`
      <h3>+ Yangi vazifa</h3>
      <div class="field">
        <label class="field-label">Xodim</label>
        <select id="tk-employee">
          ${employees.map((e) => `<option value="${e.id}">${escapeHtml(e.full_name)}</option>`).join('')}
        </select>
      </div>
      <div class="field">
        <label class="field-label">Vazifa nomi</label>
        <input id="tk-title" type="text" placeholder="Hisobot tayyorlash" />
      </div>
      <div class="field">
        <label class="field-label">Tavsif</label>
        <textarea id="tk-desc" placeholder="Batafsil izoh"></textarea>
      </div>
      <div class="field">
        <label class="field-label">Muddat</label>
        <input id="tk-deadline" type="date" />
      </div>
      <button class="btn" id="tk-submit">Berish</button>`);

    document.getElementById('tk-submit').addEventListener('click', async () => {
      const employee_id = parseInt(document.getElementById('tk-employee').value);
      const title = document.getElementById('tk-title').value.trim();
      const description = document.getElementById('tk-desc').value.trim();
      const deadline = document.getElementById('tk-deadline').value;
      if (!title) return toast('Vazifa nomini kiriting');
      try {
        await api('/api/admin/tasks', { method: 'POST', body: JSON.stringify({ employee_id, title, description, deadline }) });
        closeModal();
        toast('✅ Vazifa berildi');
        renderAdminTasks(container);
      } catch (e) { toast(e.message); }
    });
  });
}

init();
