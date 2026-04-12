const state = {
  items: [],
  selected: new Set(),
  filter: 'all',
  search: '',
  cookieTemplate: '',
  exportedTo: 'emails.txt',
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

function setCookieStatus(text, tone = 'muted') {
  els.cookieStatus.textContent = text;
  els.cookieStatus.className = `status-pill ${tone}`;
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
    tr.innerHTML = `<td colspan="6" class="empty-row">没有匹配结果。</td>`;
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

async function bootstrap() {
  try {
    const data = await api('/api/bootstrap', { method: 'GET' });
    state.cookieTemplate = data.cookieTemplate || '';
    state.exportedTo = data.emailsPath || 'emails.txt';
    els.cookiesInput.value = data.cookiesText || data.cookieTemplate || '';
    els.cookiePathHint.textContent = `文件路径：${data.cookiesPath}`;
    setCookieStatus(data.cookiesText ? '已加载' : '等待填写', data.cookiesText ? 'success' : 'muted');
    updateSummary();
    log('info', '前端已就绪');
  } catch (error) {
    log('error', error.message);
    setCookieStatus('初始化失败', 'danger');
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

async function refreshList() {
  els.lastActionHint.textContent = '正在拉取列表...';
  try {
    const data = await api('/api/list', { method: 'GET' });
    state.items = data.items || [];
    state.exportedTo = data.exportedTo || 'emails.txt';
    state.selected = new Set([...state.selected].filter((id) => state.items.some((item) => item.anonymousId === id)));
    renderTable();
    els.lastActionHint.textContent = `已刷新，共 ${data.summary.total} 条`;
    log('success', `列表已刷新，共 ${data.summary.total} 条`);
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
    renderTable();

    const successCount = (data.results || []).filter((item) => item.ok).length;
    const failedCount = (data.results || []).length - successCount;
    els.lastActionHint.textContent = `${actionLabel}完成：成功 ${successCount}，失败 ${failedCount}`;
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
