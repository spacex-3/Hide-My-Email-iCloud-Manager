const defaultAuthState = {
  available: true,
  availableMessage: '可用',
  hasProfile: false,
  appleId: '',
  region: 'us',
  regionLabel: '美国区',
  profileKey: '',
  storageId: '',
  authenticated: false,
  trustedSession: false,
  requires2FA: false,
  requires2SA: false,
  deliveryMethod: 'unknown',
  deliveryNotice: null,
  sessionDirectory: '-',
  sessionPath: '',
  cookiejarPath: '',
  cookieSnapshotPath: '',
  accountExportPath: '',
  cacheJsonPath: '',
  cachedSummary: { total: 0, active: 0, inactive: 0 },
  lastFetchAt: null,
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
  savedAccounts: [],
  lastSource: 'none',
  lastCacheAt: null,
  busy: {
    authRefresh: false,
    login: false,
    switchAccount: false,
    request2fa: false,
    verify2fa: false,
    logout: false,
    saveCookies: false,
    list: false,
    action: false,
  },
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
  accountItemTemplate: document.querySelector('#accountItemTemplate'),
  saveCookiesBtn: document.querySelector('#saveCookiesBtn'),
  loadTemplateBtn: document.querySelector('#loadTemplateBtn'),
  refreshBtn: document.querySelector('#refreshBtn'),
  selectVisibleBtn: document.querySelector('#selectVisibleBtn'),
  clearSelectionBtn: document.querySelector('#clearSelectionBtn'),
  deactivateBtn: document.querySelector('#deactivateBtn'),
  deleteBtn: document.querySelector('#deleteBtn'),
  clearLogBtn: document.querySelector('#clearLogBtn'),
  authStatusPill: document.querySelector('#authStatusPill'),
  heroAuthBadge: document.querySelector('#heroAuthBadge'),
  heroSourceBadge: document.querySelector('#heroSourceBadge'),
  heroCountBadge: document.querySelector('#heroCountBadge'),
  dataSourceBadge: document.querySelector('#dataSourceBadge'),
  visibleCountBadge: document.querySelector('#visibleCountBadge'),
  savedAccountsCount: document.querySelector('#savedAccountsCount'),
  savedAccountsList: document.querySelector('#savedAccountsList'),
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

const buttonLoadingText = new Map([
  [els.refreshAuthBtn, '检查中...'],
  [els.refreshBtn, '刷新中...'],
  [els.loginBtn, '登录中...'],
  [els.request2faBtn, '请求中...'],
  [els.verify2faBtn, '验证中...'],
  [els.logoutBtn, '退出中...'],
  [els.saveCookiesBtn, '保存中...'],
  [els.deactivateBtn, '停用中...'],
  [els.deleteBtn, '删除中...'],
]);

function initButtonLabels() {
  for (const button of buttonLoadingText.keys()) {
    if (button && !button.dataset.label) {
      button.dataset.label = button.textContent.trim();
    }
  }
}

function log(level, text) {
  const node = els.logTemplate.content.firstElementChild.cloneNode(true);
  node.querySelector('.log-time').textContent = new Date().toLocaleTimeString('zh-CN', { hour12: false });
  node.querySelector('.log-level').textContent = level.toUpperCase();
  node.querySelector('.log-level').classList.add(level);
  node.querySelector('.log-text').textContent = text;
  els.logList.prepend(node);
  while (els.logList.childElementCount > 14) {
    els.logList.removeChild(els.logList.lastElementChild);
  }
}

function sourceLabel(source) {
  if (source === 'session') return '持久化登录';
  if (source === 'cookies') return '手动 Cookies';
  if (source === 'cache') return '本地缓存';
  if (source === 'pending-2fa') return '等待 2FA';
  return '未登录';
}

function sourceTone(source) {
  if (source === 'session') return 'success';
  if (source === 'cookies' || source === 'cache' || source === 'pending-2fa') return 'warn';
  return 'muted';
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

function formatTimeText(value) {
  if (!value) return '未记录';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' });
}

function escapeHtml(text) {
  return String(text)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function anyBusy() {
  return Object.values(state.busy).some(Boolean);
}

function setButtonLoading(button, loading, loadingText) {
  if (!button) return;
  if (!button.dataset.label) {
    button.dataset.label = button.textContent.trim();
  }
  button.classList.toggle('is-loading', loading);
  button.textContent = loading ? (loadingText || buttonLoadingText.get(button) || '处理中...') : button.dataset.label;
}

function setBusy(key, busy, button) {
  state.busy[key] = busy;
  if (button) {
    setButtonLoading(button, busy, buttonLoadingText.get(button));
  }
  syncControls();
}

function setCookieStatus(text, tone = 'muted') {
  els.cookieStatus.textContent = text;
  els.cookieStatus.className = `status-pill ${tone}`;
}

function setLastAction(text, tone = 'muted') {
  els.lastActionHint.textContent = text;
  els.lastActionHint.className = `footer-state ${tone}`;
}

function updateSourceBadges() {
  const source = state.lastSource || state.auth.source || 'none';
  const label = sourceLabel(source);
  const tone = sourceTone(source);
  els.heroSourceBadge.textContent = `数据源：${label}`;
  els.heroSourceBadge.className = `status-pill ${tone}`;
  els.dataSourceBadge.textContent = `数据源：${label}`;
  els.dataSourceBadge.className = `status-pill ${tone}`;
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
    const haystack = [item.email, item.anonymousId, item.label, item.forwardTo, item.note]
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
  const visible = visibleItems().length;
  const selected = state.selected.size;

  els.totalCount.textContent = total;
  els.activeCount.textContent = active;
  els.inactiveCount.textContent = inactive;
  els.selectedCount.textContent = selected;
  els.visibleCountBadge.textContent = `可见 ${visible}`;
  els.exportHint.textContent = `导出文件：${state.exportedTo}`;
  els.heroCountBadge.textContent = `${total} 条别名`;
  updateSourceBadges();
  syncControls();
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
    const checked = state.selected.has(item.anonymousId);
    const statusText = item.isActive ? '启用中' : '已停用';
    const statusClass = item.isActive ? 'tag success' : 'tag muted';
    tr.dataset.id = item.anonymousId;
    tr.className = checked ? 'is-selected' : '';
    tr.innerHTML = `
      <td class="checkbox-col">
        <input type="checkbox" data-id="${item.anonymousId}" ${checked ? 'checked' : ''} />
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

function applyAuthStatus(status) {
  state.auth = { ...defaultAuthState, ...(status || {}) };
  const auth = state.auth;

  if (auth.appleId) {
    els.appleIdInput.value = auth.appleId;
  }
  els.regionSelect.value = auth.region || 'us';

  const authText = authPillText(auth);
  const authTone = authPillTone(auth);
  els.authStatusPill.textContent = authText;
  els.authStatusPill.className = `status-pill ${authTone}`;
  els.heroAuthBadge.textContent = authText;
  els.heroAuthBadge.className = `status-pill ${authTone}`;

  els.authAccount.textContent = auth.appleId || '-';
  els.authRegion.textContent = auth.regionLabel || regionText(auth.region || 'us');

  let notice = auth.availableMessage;
  if (auth.authenticated) {
    notice = `已登录，可直接拉取 Hide My Email 列表（${sourceLabel(auth.source)}）`;
    state.lastSource = auth.source || state.lastSource || 'session';
  } else if (auth.requires2FA) {
    notice = `当前需要 2FA：${deliveryText(auth.deliveryMethod)}`;
    if (auth.deliveryNotice) {
      notice += `；${auth.deliveryNotice}`;
    }
    state.lastSource = 'pending-2fa';
  } else if (auth.hasProfile) {
    notice = '检测到本地会话文件，但当前未认证，可能已过期；可重新输入密码登录。';
  }
  els.authNotice.textContent = notice;
  els.authSessionDir.textContent = auth.sessionDirectory || '-';
  const files = [auth.sessionPath, auth.cookiejarPath].filter(Boolean);
  els.authSessionFiles.textContent = files.length ? files.join(' | ') : '-';

  let hint = '登录态会保存在本地 `.pyicloud/`。只保存 session / cookie 快照和账号资料，不保存密码明文。';
  if (!auth.available) {
    hint = auth.availableMessage;
  } else if (auth.authenticated) {
    hint = `当前区服：${auth.regionLabel || regionText(auth.region)}；可直接切换到其他已保存账号，无需重新登录或 2FA。`;
  } else if (auth.requires2FA) {
    hint = '先触发验证码或设备提示，再输入验证码完成验证。验证成功后会把当前账号加入已保存列表。';
  }
  els.authHint.textContent = hint;

  if (auth.authenticated) {
    els.passwordInput.value = '';
    els.twoFactorCodeInput.value = '';
  }
}

function applySavedAccounts(accounts) {
  state.savedAccounts = Array.isArray(accounts) ? accounts : [];
  els.savedAccountsCount.textContent = `${state.savedAccounts.length} 个账号`;
  renderSavedAccounts();
}

function createBadge(text, tone = 'muted') {
  return `<span class="status-pill ${tone}">${escapeHtml(text)}</span>`;
}

function renderSavedAccounts() {
  els.savedAccountsList.innerHTML = '';
  if (!state.savedAccounts.length) {
    const empty = document.createElement('div');
    empty.className = 'saved-account-empty';
    empty.textContent = '还没有已保存账号。首次登录成功后会出现在这里。';
    els.savedAccountsList.appendChild(empty);
    return;
  }

  for (const account of state.savedAccounts) {
    const node = els.accountItemTemplate.content.firstElementChild.cloneNode(true);
    node.dataset.profileKey = account.profileKey;
    if (account.isActive) node.classList.add('is-active');

    node.querySelector('.saved-account-title').textContent = account.appleId;
    const badges = [];
    badges.push(createBadge(account.regionLabel || regionText(account.region), 'muted'));
    if (account.isActive) badges.push(createBadge('当前', 'success'));
    else if (account.lastKnownAuthenticated) badges.push(createBadge('可直连', 'success'));
    else if (account.hasSessionFiles) badges.push(createBadge('需校验', 'warn'));
    if (account.cachedListAvailable) {
      const total = account.cachedSummary?.total ?? 0;
      badges.push(createBadge(`缓存 ${total}`, 'warn'));
    }
    node.querySelector('.saved-account-badges').innerHTML = badges.join('');

    node.querySelector('.saved-account-subtitle').textContent = `${account.regionLabel || regionText(account.region)} · ${account.hasSessionFiles ? '已保存 session' : '无 session 文件'}`;
    const metaParts = [];
    if (account.lastUsedAt) metaParts.push(`最近切换 ${formatTimeText(account.lastUsedAt)}`);
    if (account.lastFetchAt) metaParts.push(`列表更新 ${formatTimeText(account.lastFetchAt)}`);
    if (!metaParts.length) metaParts.push('尚未拉取列表');
    node.querySelector('.saved-account-meta').textContent = metaParts.join(' · ');

    const action = node.querySelector('.saved-account-action');
    if (account.isActive) {
      action.textContent = '当前';
    }
    node.disabled = anyBusy() || account.isActive;
    els.savedAccountsList.appendChild(node);
  }
}

function applyCachedList(cachedList, { source = 'cache', preserveSelection = false } = {}) {
  if (!cachedList || !Array.isArray(cachedList.items)) return false;
  state.items = cachedList.items;
  state.exportedTo = cachedList.activeExportPath || 'emails.txt';
  state.lastSource = source;
  state.lastCacheAt = cachedList.updatedAt || null;
  if (preserveSelection) {
    state.selected = new Set([...state.selected].filter((id) => state.items.some((item) => item.anonymousId === id)));
  } else {
    state.selected.clear();
  }
  renderTable();
  return true;
}

function applyContext(payload) {
  if (!payload || typeof payload !== 'object') return;
  if (payload.cookiesText !== undefined) {
    els.cookiesInput.value = payload.cookiesText || payload.cookieTemplate || '';
  }
  if (payload.cookieTemplate !== undefined) {
    state.cookieTemplate = payload.cookieTemplate || '';
  }
  if (payload.cookiesPath) {
    els.cookiePathHint.textContent = `文件路径：${payload.cookiesPath}`;
  }
  if (payload.authStatus) {
    applyAuthStatus(payload.authStatus || defaultAuthState);
  }
  if (payload.savedAccounts) {
    applySavedAccounts(payload.savedAccounts);
  }
  if (payload.cachedList) {
    applyCachedList(payload.cachedList, { source: 'cache' });
  }
  if (payload.emailsPath) {
    state.exportedTo = payload.emailsPath;
  }
  updateSummary();
}

function syncControls() {
  const auth = state.auth;
  const selected = state.selected.size > 0;
  const busy = anyBusy();
  const visible = visibleItems().length;

  els.loginBtn.disabled = !auth.available || state.busy.login || state.busy.request2fa || state.busy.verify2fa || state.busy.logout || state.busy.switchAccount;
  els.refreshAuthBtn.disabled = !auth.available || state.busy.authRefresh || state.busy.login || state.busy.switchAccount;
  els.request2faBtn.disabled = !auth.available || !auth.requires2FA || state.busy.request2fa || state.busy.verify2fa || state.busy.login;
  els.verify2faBtn.disabled = !auth.available || !auth.requires2FA || !els.twoFactorCodeInput.value.trim() || state.busy.verify2fa;
  els.logoutBtn.disabled = !auth.available || !auth.hasProfile || state.busy.logout || state.busy.login || state.busy.switchAccount;

  els.saveCookiesBtn.disabled = state.busy.saveCookies;
  els.loadTemplateBtn.disabled = state.busy.saveCookies;
  els.refreshBtn.disabled = state.busy.list || state.busy.action || state.busy.switchAccount;
  els.selectVisibleBtn.disabled = busy || visible === 0;
  els.clearSelectionBtn.disabled = busy || !selected;
  els.deactivateBtn.disabled = busy || !selected;
  els.deleteBtn.disabled = busy || !selected;
  els.toggleAll.disabled = busy || visible === 0;

  renderSavedAccounts();
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  const raw = await response.text();
  let data = {};
  if (raw) {
    try {
      data = JSON.parse(raw);
    } catch {
      throw new Error(raw.slice(0, 160) || '服务返回了无效响应');
    }
  }
  if (!response.ok) {
    throw new Error(data.error || `请求失败（HTTP ${response.status}）`);
  }
  return data;
}

async function runAsyncAction(key, button, fn) {
  setBusy(key, true, button);
  try {
    return await fn();
  } finally {
    setBusy(key, false, button);
  }
}

async function refreshBootstrap(silent = true) {
  const data = await api('/api/bootstrap', { method: 'GET' });
  applyContext(data);
  setCookieStatus((data.cookiesText || '').trim() ? '已加载' : '等待填写', (data.cookiesText || '').trim() ? 'success' : 'muted');
  if (!silent) log('info', '页面状态已同步');
  return data;
}

async function bootstrap() {
  try {
    await refreshBootstrap(true);
    setLastAction('界面已就绪', 'success');
    log('info', '前端已就绪');
  } catch (error) {
    setCookieStatus('初始化失败', 'danger');
    setLastAction('初始化失败', 'danger');
    applyAuthStatus({ ...defaultAuthState, available: false, availableMessage: error.message });
    log('error', error.message);
  }
}

async function saveCookies() {
  await runAsyncAction('saveCookies', els.saveCookiesBtn, async () => {
    try {
      const data = await api('/api/cookies/save', {
        method: 'POST',
        body: JSON.stringify({ text: els.cookiesInput.value }),
      });
      applyContext(data);
      setCookieStatus('已保存', 'success');
      setLastAction('Cookies 已保存', 'success');
      log('success', 'cookies.txt 已保存');
    } catch (error) {
      setCookieStatus('保存失败', 'danger');
      setLastAction('Cookies 保存失败', 'danger');
      log('error', error.message);
    }
  });
}

async function refreshAuthStatus() {
  await runAsyncAction('authRefresh', els.refreshAuthBtn, async () => {
    try {
      const data = await api('/api/auth/status', { method: 'GET' });
      applyContext(data);
      setLastAction(`会话状态：${authPillText(state.auth)}`, 'muted');
      log('info', `会话状态：${authPillText(state.auth)}`);
    } catch (error) {
      setLastAction('会话检查失败', 'danger');
      log('error', error.message);
    }
  });
}

async function loginWithAccount() {
  const appleId = els.appleIdInput.value.trim();
  const password = els.passwordInput.value;
  const region = els.regionSelect.value;
  if (!appleId || !password) {
    log('info', '请先填写 Apple ID 和密码');
    return;
  }

  await runAsyncAction('login', els.loginBtn, async () => {
    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ appleId, password, region }),
      });
      applyContext(data);
      setLastAction(data.message || '登录请求已提交', data.status?.authenticated ? 'success' : 'warn');
      log(data.status?.authenticated ? 'success' : 'info', data.message || '登录请求已提交');
      if (data.status?.requires2FA) {
        els.twoFactorCodeInput.focus();
      }
    } catch (error) {
      setLastAction('登录失败', 'danger');
      log('error', error.message);
    }
  });
}

async function switchAccount(profileKey) {
  if (!profileKey) return;
  await runAsyncAction('switchAccount', null, async () => {
    try {
      const data = await api('/api/auth/switch', {
        method: 'POST',
        body: JSON.stringify({ profileKey }),
      });
      applyContext(data);
      if (data.cachedList) {
        applyCachedList(data.cachedList, { source: data.status?.authenticated ? 'cache' : 'cache' });
      }
      setLastAction(data.message || '已切换账号', data.status?.authenticated ? 'success' : 'warn');
      log(data.status?.authenticated ? 'success' : 'info', data.message || '已切换账号');
    } catch (error) {
      setLastAction('切换账号失败', 'danger');
      log('error', error.message);
    }
  });
}

async function requestTwoFactorCode() {
  await runAsyncAction('request2fa', els.request2faBtn, async () => {
    try {
      const data = await api('/api/auth/request-2fa', { method: 'POST', body: '{}' });
      applyContext(data);
      setLastAction(data.message || '已触发验证码', data.status?.deliveryTriggered ? 'success' : 'warn');
      log(data.status?.deliveryTriggered ? 'success' : 'info', data.message || '已触发验证码');
      els.twoFactorCodeInput.focus();
    } catch (error) {
      setLastAction('验证码请求失败', 'danger');
      log('error', error.message);
    }
  });
}

async function verifyTwoFactorCode() {
  const code = els.twoFactorCodeInput.value.trim();
  if (!code) {
    log('info', '请先输入验证码');
    return;
  }

  await runAsyncAction('verify2fa', els.verify2faBtn, async () => {
    try {
      const data = await api('/api/auth/verify-2fa', {
        method: 'POST',
        body: JSON.stringify({ code }),
      });
      applyContext(data);
      setLastAction(data.message || '验证码已提交', data.status?.authenticated ? 'success' : 'warn');
      log(data.status?.authenticated ? 'success' : 'info', data.message || '验证码已提交');
    } catch (error) {
      setLastAction('验证码校验失败', 'danger');
      log('error', error.message);
    }
  });
}

async function logoutAccount() {
  if (!window.confirm('确认退出当前账号并清理本地持久化 session / 缓存吗？')) {
    return;
  }

  await runAsyncAction('logout', els.logoutBtn, async () => {
    try {
      const data = await api('/api/auth/logout', { method: 'POST', body: '{}' });
      applyContext(data);
      if (!data.cachedList) {
        state.items = [];
        state.selected.clear();
        state.lastSource = 'none';
        renderTable();
      }
      setLastAction(data.message || '本地会话已清除', 'muted');
      log('info', data.message || '已退出本地会话');
    } catch (error) {
      setLastAction('退出会话失败', 'danger');
      log('error', error.message);
    }
  });
}

async function refreshList() {
  await runAsyncAction('list', els.refreshBtn, async () => {
    setLastAction('正在拉取列表...', 'warn');
    try {
      const data = await api('/api/list', { method: 'GET' });
      state.items = data.items || [];
      state.exportedTo = data.emailsPath || state.auth.accountExportPath || 'emails.txt';
      state.lastSource = data.source || state.auth.source || 'none';
      state.lastCacheAt = data.cachedList?.updatedAt || state.lastCacheAt;
      state.selected = new Set([...state.selected].filter((id) => state.items.some((item) => item.anonymousId === id)));
      applyContext(data);
      renderTable();
      setLastAction(`已刷新，共 ${data.summary.total} 条（${sourceLabel(state.lastSource)}）`, 'success');
      log('success', `列表已刷新，共 ${data.summary.total} 条（${sourceLabel(state.lastSource)}）`);
    } catch (error) {
      setLastAction('刷新失败', 'danger');
      log('error', error.message);
    }
  });
}

async function performAction(action) {
  const ids = [...state.selected];
  if (!ids.length) {
    log('info', '请先选择要操作的条目');
    return;
  }
  const label = action === 'deactivate' ? '停用' : '删除';
  if (!window.confirm(`确认${label} ${ids.length} 个条目吗？`)) {
    return;
  }

  const button = action === 'deactivate' ? els.deactivateBtn : els.deleteBtn;
  await runAsyncAction('action', button, async () => {
    setLastAction(`正在${label} ${ids.length} 个条目...`, 'warn');
    try {
      const data = await api('/api/action', {
        method: 'POST',
        body: JSON.stringify({ action, ids }),
      });
      state.items = data.items || [];
      state.selected.clear();
      state.lastSource = data.source || state.lastSource;
      applyContext(data);
      renderTable();
      const successCount = (data.results || []).filter((item) => item.ok).length;
      const failedCount = (data.results || []).length - successCount;
      setLastAction(`${label}完成：成功 ${successCount}，失败 ${failedCount}`, failedCount ? 'warn' : 'success');
      log('success', `${label}完成：成功 ${successCount}，失败 ${failedCount}`);
      for (const result of data.results || []) {
        log(result.ok ? 'info' : 'error', `${label} ${result.email || result.anonymousId}：${result.message}`);
      }
    } catch (error) {
      setLastAction(`${label}失败`, 'danger');
      log('error', error.message);
    }
  });
}

function selectVisibleRows() {
  for (const item of visibleItems()) {
    state.selected.add(item.anonymousId);
  }
  renderTable();
  setLastAction(`已选择 ${state.selected.size} 个条目`, 'muted');
}

function clearSelection() {
  state.selected.clear();
  renderTable();
  setLastAction('已清空选择', 'muted');
}

function toggleSelection(id, nextValue = null) {
  if (!id) return;
  const checked = nextValue ?? !state.selected.has(id);
  if (checked) state.selected.add(id);
  else state.selected.delete(id);
  renderTable();
}

els.saveCookiesBtn.addEventListener('click', saveCookies);
els.loadTemplateBtn.addEventListener('click', () => {
  els.cookiesInput.value = state.cookieTemplate || '';
  setCookieStatus('已载入模板', 'muted');
  setLastAction('已载入 Cookies 模板', 'muted');
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
  setLastAction('日志已清空', 'muted');
});

els.searchInput.addEventListener('input', (event) => {
  state.search = event.target.value;
  renderTable();
});

els.filterSelect.addEventListener('change', (event) => {
  state.filter = event.target.value;
  renderTable();
});

els.passwordInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    loginWithAccount();
  }
});

els.twoFactorCodeInput.addEventListener('input', syncControls);
els.twoFactorCodeInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    verifyTwoFactorCode();
  }
});

els.cookiesInput.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key === 'Enter') {
    event.preventDefault();
    saveCookies();
  }
});

els.savedAccountsList.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  const button = target.closest('.saved-account-item');
  if (!(button instanceof HTMLButtonElement)) return;
  switchAccount(button.dataset.profileKey);
});

els.tableBody.addEventListener('change', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLInputElement) || target.type !== 'checkbox') return;
  toggleSelection(target.dataset.id, target.checked);
});

els.tableBody.addEventListener('click', (event) => {
  const target = event.target;
  if (!(target instanceof HTMLElement)) return;
  if (target.closest('input, button, a, code')) return;
  const row = target.closest('tr[data-id]');
  if (!row) return;
  toggleSelection(row.dataset.id);
});

els.toggleAll.addEventListener('change', (event) => {
  const checked = event.target.checked;
  const ids = visibleItems().map((item) => item.anonymousId);
  ids.forEach((id) => {
    if (checked) state.selected.add(id);
    else state.selected.delete(id);
  });
  renderTable();
});

initButtonLabels();
bootstrap();
