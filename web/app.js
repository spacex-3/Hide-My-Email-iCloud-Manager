const defaultAuthState = {
  available: true,
  availableMessage: '可用',
  hasProfile: false,
  appleId: '',
  region: 'us',
  regionLabel: '美国区',
  authenticated: false,
  trustedSession: false,
  requires2FA: false,
  requires2SA: false,
  deliveryMethod: 'unknown',
  deliveryNotice: null,
  sessionDirectory: '-',
  sessionPath: '',
  cookiejarPath: '',
  source: 'none',
};

const state = {
  items: [],
  selected: new Set(),
  filter: 'all',
  search: '',
  cookieTemplate: '',
  exportedTo: 'emails.txt',
  auth: { ...defaultAuthState },
};

const els = {
  cookiesInput: document.querySelector('#cookiesInput'),
  cookiePathHint: document.querySelector('#cookiePathHint'),
  cookieStatus: document.querySelector('#cookieStatus'),
  totalCount: document.querySelector('#totalCount'),
  activeCount: document.querySelector('#activeCount'),
  inactiveCount: document.querySelector('#inactiveCount'),
  selectedCount: document.querySelector('#selectedCount'),
  searchInput: document.querySelector('#searchInput'),
  filterSelect: document.querySelector('#filterSelect'),
  tableBody: document.querySelector('#tableBody'),
  toggleAll: document.querySelector('#toggleAll'),
  exportHint: document.querySelector('#exportHint'),
  lastActionHint: document.querySelector('#lastActionHint'),
  logList: document.querySelector('#logList'),
  logTemplate: document.querySelector('#logItemTemplate'),
  saveCookiesBtn: document.querySelector('#saveCookiesBtn'),
  loadTemplateBtn: document.querySelector('#loadTemplateBtn'),
  refreshBtn: document.querySelector('#refreshBtn'),
  selectVisibleBtn: document.querySelector('#selectVisibleBtn'),
  clearSelectionBtn: document.querySelector('#clearSelectionBtn'),
  deactivateBtn: document.querySelector('#deactivateBtn'),
  deleteBtn: document.querySelector('#deleteBtn'),
  clearLogBtn: document.querySelector('#clearLogBtn'),
  authStatusPill: document.querySelector('#authStatusPill'),
  regionSelect: document.querySelector('#regionSelect'),
  appleIdInput: document.querySelector('#appleIdInput'),
  passwordInput: document.querySelector('#passwordInput'),
  loginBtn: document.querySelector('#loginBtn'),
  refreshAuthBtn: document.querySelector('#refreshAuthBtn'),
  request2faBtn: document.querySelector('#request2faBtn'),
  verify2faBtn: document.querySelector('#verify2faBtn'),
  logoutBtn: document.querySelector('#logoutBtn'),
  twoFactorCodeInput: document.querySelector('#twoFactorCodeInput'),
  authAccount: document.querySelector('#authAccount'),
  authRegion: document.querySelector('#authRegion'),
  authNotice: document.querySelector('#authNotice'),
  authSessionDir: document.querySelector('#authSessionDir'),
  authSessionFiles: document.querySelector('#authSessionFiles'),
  authHint: document.querySelector('#authHint'),
};

function log(level, text) {
  const node = els.logTemplate.content.firstElementChild.cloneNode(true);
  node.querySelector('.log-time').textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  node.querySelector('.log-level').textContent = level.toUpperCase();
  node.querySelector('.log-level').classList.add(level);
  node.querySelector('.log-text').textContent = text;
  els.logList.prepend(node);

  while (els.logList.childElementCount > 12) {
    els.logList.removeChild(els.logList.lastElementChild);
  }
}

function sourceLabel(source) {
  if (source === 'session') return '持久化登录';
  if (source === 'cookies') return '手动 Cookies';
  if (source === 'pending-2fa') return '等待 2FA';
  return '未登录';
}

function authPillText(status) {
  if (!status.available) return '依赖缺失';
  if (status.authenticated) return '已登录';
  if (status.requires2FA) return '等待 2FA';
  if (status.hasProfile) return '已保存会话';
  return '未登录';
}

function authPillTone(status) {
  if (!status.available) return 'danger';
  if (status.authenticated) return 'success';
  if (status.requires2FA) return 'warn';
  return 'muted';
}

function setCookieStatus(text, tone = 'muted') {
  els.cookieStatus.textContent = text;
  els.cookieStatus.className = `status-pill ${tone}`;
}

function applyAuthStatus(status) {
  state.auth = { ...defaultAuthState, ...(status || {}) };
  const auth = state.auth;

  if (auth.appleId) {
    els.appleIdInput.value = auth.appleId;
  }
  els.regionSelect.value = auth.region || 'us';

  els.authStatusPill.textContent = authPillText(auth);
  els.authStatusPill.className = `status-pill ${authPillTone(auth)}`;
  els.authAccount.textContent = auth.appleId || '-';
  els.authRegion.textContent = auth.regionLabel || regionText(auth.region || 'us');

  let notice = auth.availableMessage;
  if (auth.authenticated) {
    notice = `已登录，可直接拉取 Hide My Email 列表（${sourceLabel(auth.source)}）`;
  } else if (auth.requires2FA) {
    const delivery = deliveryText(auth.deliveryMethod);
    notice = `当前需要 2FA：${delivery}`;
    if (auth.deliveryNotice) {
      notice += `；${auth.deliveryNotice}`;
    }
  } else if (auth.hasProfile) {
    notice = '检测到本地会话文件，但当前未认证，可能已过期；可重新输入密码登录。';
  }
  els.authNotice.textContent = notice;
  els.authSessionDir.textContent = auth.sessionDirectory || '-';

  const sessionFiles = [auth.sessionPath, auth.cookiejarPath].filter(Boolean);
  els.authSessionFiles.textContent = sessionFiles.length ? sessionFiles.join(' | ') : '-';

  let hint = '登录态会保存在本地 `.pyicloud/`。这能尽量延长复用时间，但 Apple 仍可能定期要求重新登录或重新 2FA。';
  if (!auth.available) {
    hint = auth.availableMessage;
  } else if (auth.authenticated) {
    hint = `当前区服：${auth.regionLabel || regionText(auth.region)}；列表与停用/删除将优先复用持久化 session。`;
  } else if (auth.requires2FA) {
    hint = '先触发验证码/设备提示，再输入验证码完成验证。验证成功后会导出当前 cookies 快照。';
  }
  els.authHint.textContent = hint;

  els.loginBtn.disabled = !auth.available;
  els.refreshAuthBtn.disabled = !auth.available;
  els.request2faBtn.disabled = !auth.available || !auth.requires2FA;
  els.verify2faBtn.disabled = !auth.available || !auth.requires2FA;
  els.logoutBtn.disabled = !auth.available || !auth.hasProfile;

  if (auth.authenticated) {
    els.passwordInput.value = '';
    els.twoFactorCodeInput.value = '';
  }
}

function regionText(region) {
  return region === 'cn' ? '中国区' : '美国区';
}

function deliveryText(method) {
  const mapping = {
    sms: '短信验证码',
    trusted_device: 'Apple 设备确认',
    security_key: '安全密钥',
    unknown: '待确认',
  };
  return mapping[method] || method || '待确认';
}

function applyBootstrap(data) {
  state.cookieTemplate = data.cookieTemplate || '';
  state.exportedTo = data.emailsPath || 'emails.txt';
  els.cookiesInput.value = data.cookiesText || data.cookieTemplate || '';
  els.cookiePathHint.textContent = `文件路径：${data.cookiesPath}`;
  setCookieStatus(data.cookiesText ? '已加载' : '等待填写', data.cookiesText ? 'success' : 'muted');
  applyAuthStatus(data.authStatus || defaultAuthState);
  updateSummary();
}

function visibleItems() {
  const keyword = state.search.trim().toLowerCase();
  return state.items.filter((item) => {
    const matchesFilter =
      state.filter === 'all' ||
      (state.filter === 'active' && item.isActive) ||
      (state.filter === 'inactive' && !item.isActive);

    if (!matchesFilter) return false;
    if (!keyword) return true;

    const haystack = [item.email, item.anonymousId, item.label, item.forwardTo]
      .filter(Boolean)
      .join(' ')
      .toLowerCase();
    return haystack.includes(keyword);
  });
}

function updateSummary() {
  const total = state.items.length;
  const active = state.items.filter((item) => item.isActive).length;
  const inactive = total - active;

  els.totalCount.textContent = total;
  els.activeCount.textContent = active;
  els.inactiveCount.textContent = inactive;
  els.selectedCount.textContent = state.selected.size;
  els.exportHint.textContent = `导出文件：${state.exportedTo}`;
}

function renderTable() {
  const rows = visibleItems();
  els.tableBody.innerHTML = '';

  if (!rows.length) {
    const tr = document.createElement('tr');
    tr.innerHTML = `<td colspan="6" class="empty-row">${state.items.length ? '没有匹配结果。' : '还没有数据，先登录 iCloud 或保存 Cookies 后点击“刷新列表”。'}</td>`;
    els.tableBody.appendChild(tr);
    els.toggleAll.checked = false;
    updateSummary();
    return;
  }

  for (const item of rows) {
    const tr = document.createElement('tr');
    const isChecked = state.selected.has(item.anonymousId);
    const statusText = item.isActive ? '启用中' : '已停用';
    const statusClass = item.isActive ? 'tag success' : 'tag muted';
    tr.innerHTML = `
      <td class="checkbox-col">
        <input type="checkbox" data-id="${item.anonymousId}" ${isChecked ? 'checked' : ''} />
      </td>
      <td>
        <div class="cell-primary">${escapeHtml(item.email || '-')}</div>
        <div class="cell-secondary">${escapeHtml(item.note || '')}</div>
      </td>
      <td><span class="${statusClass}">${statusText}</span></td>
      <td>${escapeHtml(item.label || '-')}</td>
      <td>${escapeHtml(item.forwardTo || '-')}</td>
      <td><code title="${escapeHtml(item.anonymousId)}">${escapeHtml(shortId(item.anonymousId))}</code></td>
    `;
    els.tableBody.appendChild(tr);
  }

  const ids = rows.map((item) => item.anonymousId);
  els.toggleAll.checked = ids.length > 0 && ids.every((id) => state.selected.has(id));
  updateSummary();
}

function shortId(id) {
  if (!id) return '-';
  if (id.length <= 18) return id;
  return `${id.slice(0, 8)}…${id.slice(-8)}`;
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.error || '请求失败');
  }
  return data;
}

async function refreshBootstrap(silent = true) {
  const data = await api('/api/bootstrap', { method: 'GET' });
  applyBootstrap(data);
  if (!silent) {
    log('info', '页面状态已同步');
  }
  return data;
}

async function bootstrap() {
  try {
    await refreshBootstrap(true);
    log('info', '前端已就绪');
  } catch (error) {
    log('error', error.message);
    setCookieStatus('初始化失败', 'danger');
    applyAuthStatus({ ...defaultAuthState, available: false, availableMessage: error.message });
  }
}

async function saveCookies() {
  try {
    await api('/api/cookies/save', {
      method: 'POST',
      body: JSON.stringify({ text: els.cookiesInput.value }),
    });
    setCookieStatus('已保存', 'success');
    log('success', 'cookies.txt 已保存');
  } catch (error) {
    setCookieStatus('保存失败', 'danger');
    log('error', error.message);
  }
}

async function refreshAuthStatus() {
  try {
    const data = await api('/api/auth/status', { method: 'GET' });
    applyAuthStatus(data.status || defaultAuthState);
    log('info', `会话状态：${authPillText(state.auth)}`);
  } catch (error) {
    log('error', error.message);
  }
}

async function loginWithAccount() {
  const appleId = els.appleIdInput.value.trim();
  const password = els.passwordInput.value;
  const region = els.regionSelect.value;

  if (!appleId || !password) {
    log('info', '请先填写 Apple ID 和密码');
    return;
  }

  try {
    const data = await api('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ appleId, password, region }),
    });
    applyAuthStatus(data.status || defaultAuthState);
    await refreshBootstrap(true);
    log(data.status?.authenticated ? 'success' : 'info', data.message || '登录请求已提交');

    if (data.status?.authenticated) {
      els.lastActionHint.textContent = `已登录（${regionText(region)}）`;
    } else if (data.status?.requires2FA) {
      els.lastActionHint.textContent = '等待 2FA 验证';
    }
  } catch (error) {
    log('error', error.message);
  }
}

async function requestTwoFactorCode() {
  try {
    const data = await api('/api/auth/request-2fa', { method: 'POST', body: '{}' });
    applyAuthStatus(data.status || defaultAuthState);
    log(data.status?.deliveryTriggered ? 'success' : 'info', data.message || '已触发验证码');
  } catch (error) {
    log('error', error.message);
  }
}

async function verifyTwoFactorCode() {
  const code = els.twoFactorCodeInput.value.trim();
  if (!code) {
    log('info', '请先输入验证码');
    return;
  }

  try {
    const data = await api('/api/auth/verify-2fa', {
      method: 'POST',
      body: JSON.stringify({ code }),
    });
    applyAuthStatus(data.status || defaultAuthState);
    await refreshBootstrap(true);
    log(data.status?.authenticated ? 'success' : 'info', data.message || '验证码已提交');
  } catch (error) {
    log('error', error.message);
  }
}

async function logoutAccount() {
  if (!window.confirm('确认清除本地持久化 session 吗？')) {
    return;
  }

  try {
    const data = await api('/api/auth/logout', { method: 'POST', body: '{}' });
    applyAuthStatus(data.status || defaultAuthState);
    state.items = [];
    state.selected.clear();
    renderTable();
    await refreshBootstrap(true);
    els.lastActionHint.textContent = '本地会话已清除';
    log('info', data.message || '已退出本地会话');
  } catch (error) {
    log('error', error.message);
  }
}

async function refreshList() {
  els.lastActionHint.textContent = '正在拉取列表...';
  try {
    const data = await api('/api/list', { method: 'GET' });
    state.items = data.items || [];
    state.exportedTo = data.exportedTo || 'emails.txt';
    state.selected = new Set([...state.selected].filter((id) => state.items.some((item) => item.anonymousId === id)));
    if (data.authStatus) {
      applyAuthStatus(data.authStatus);
    }
    renderTable();
    els.lastActionHint.textContent = `已刷新，共 ${data.summary.total} 条（${sourceLabel(data.source)}）`;
    log('success', `列表已刷新，共 ${data.summary.total} 条（${sourceLabel(data.source)}）`);
  } catch (error) {
    els.lastActionHint.textContent = '刷新失败';
    log('error', error.message);
  }
}

async function performAction(action) {
  const ids = [...state.selected];
  if (!ids.length) {
    log('info', '请先选择要操作的条目');
    return;
  }

  const actionLabel = action === 'deactivate' ? '停用' : '删除';
  if (!window.confirm(`确认${actionLabel} ${ids.length} 个条目吗？`)) {
    return;
  }

  els.lastActionHint.textContent = `正在${actionLabel} ${ids.length} 个条目...`;

  try {
    const data = await api('/api/action', {
      method: 'POST',
      body: JSON.stringify({ action, ids }),
    });
    state.items = data.items || [];
    state.exportedTo = data.exportedTo || 'emails.txt';
    state.selected = new Set();
    if (data.authStatus) {
      applyAuthStatus(data.authStatus);
    }
    renderTable();

    const successCount = (data.results || []).filter((item) => item.ok).length;
    const failedCount = (data.results || []).length - successCount;
    els.lastActionHint.textContent = `${actionLabel}完成：成功 ${successCount}，失败 ${failedCount}（${sourceLabel(data.source)}）`;
    log('success', `${actionLabel}完成：成功 ${successCount}，失败 ${failedCount}`);

    for (const result of data.results || []) {
      const level = result.ok ? 'info' : 'error';
      log(level, `${actionLabel} ${result.email || result.anonymousId}：${result.message}`);
    }
  } catch (error) {
    els.lastActionHint.textContent = `${actionLabel}失败`;
    log('error', error.message);
  }
}

function selectVisibleRows() {
  for (const item of visibleItems()) {
    state.selected.add(item.anonymousId);
  }
  renderTable();
}

function clearSelection() {
  state.selected.clear();
  renderTable();
}

els.saveCookiesBtn.addEventListener('click', saveCookies);
els.loadTemplateBtn.addEventListener('click', () => {
  els.cookiesInput.value = state.cookieTemplate || '';
  setCookieStatus('已载入模板', 'muted');
  log('info', '已载入 cookies 模板');
});
els.refreshBtn.addEventListener('click', refreshList);
els.refreshAuthBtn.addEventListener('click', refreshAuthStatus);
els.loginBtn.addEventListener('click', loginWithAccount);
els.request2faBtn.addEventListener('click', requestTwoFactorCode);
els.verify2faBtn.addEventListener('click', verifyTwoFactorCode);
els.logoutBtn.addEventListener('click', logoutAccount);
els.selectVisibleBtn.addEventListener('click', selectVisibleRows);
els.clearSelectionBtn.addEventListener('click', clearSelection);
els.deactivateBtn.addEventListener('click', () => performAction('deactivate'));
els.deleteBtn.addEventListener('click', () => performAction('delete'));
els.clearLogBtn.addEventListener('click', () => {
  els.logList.innerHTML = '';
});

els.searchInput.addEventListener('input', (event) => {
  state.search = event.target.value;
  renderTable();
});

els.filterSelect.addEventListener('change', (event) => {
  state.filter = event.target.value;
  renderTable();
});

els.tableBody.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;

  const id = target.dataset.id;
  if (!id) return;

  if (target.checked) {
    state.selected.add(id);
  } else {
    state.selected.delete(id);
  }
  renderTable();
});

els.toggleAll.addEventListener('change', (event) => {
  const checked = event.target.checked;
  const ids = visibleItems().map((item) => item.anonymousId);
  if (checked) {
    ids.forEach((id) => state.selected.add(id));
  } else {
    ids.forEach((id) => state.selected.delete(id));
  }
  renderTable();
});

bootstrap();
