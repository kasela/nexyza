(function(){
  const cfgEl = document.getElementById('connector-sync-config');
  if (!cfgEl) return;
  let cfg = {};
  try { cfg = JSON.parse(cfgEl.textContent || '{}'); } catch (e) { return; }

  const connectorMap = new Map((cfg.connectors || []).map((item) => [String(item.id), item]));
  const retryBaseUrl = cfg.retryBaseUrl || '';

  const updateSummary = (summary) => {
    if (!summary) return;
    document.querySelectorAll('#connector-summary-panel [data-summary-key]').forEach((el) => {
      const key = el.getAttribute('data-summary-key');
      if (Object.prototype.hasOwnProperty.call(summary, key)) el.textContent = summary[key];
    });
  };

  const updateCard = (item) => {
    if (!item || !item.id) return;
    const statusEl = document.getElementById(`sync-status-${item.id}`);
    const nextEl = document.getElementById(`next-sync-${item.id}`);
    if (statusEl) {
      const message = item.status === 'ok' ? `Last sync: ${item.last_synced_human}` : (item.sync_error || item.status_label);
      statusEl.innerHTML = `<span style="color:${item.status_color};">${item.status_dot} ${message}</span>`;
    }
    if (nextEl) nextEl.textContent = `Next: ${item.next_sync_human}`;
  };

  const renderHistory = (connectorId, items) => {
    const wrap = document.querySelector(`[data-connector-history-items="${connectorId}"]`);
    if (!wrap) return;
    if (!items || !items.length) {
      wrap.innerHTML = '<div style="color:#64748b;font-size:11px;">No sync history yet.</div>';
      return;
    }
    wrap.innerHTML = items.map((item) => {
      const tone = item.status === 'ok' ? '#34d399' : item.status === 'error' ? '#f87171' : '#fbbf24';
      const retryBtn = item.can_retry ? `<button type="button" data-retry-log="${item.id}" style="padding:4px 8px;border-radius:8px;border:1px solid rgba(239,68,68,.2);background:rgba(239,68,68,.08);color:#fca5a5;font-size:10px;cursor:pointer;">Retry</button>` : '';
      const meta = item.completed_human || item.started_human || '';
      const msg = item.status === 'error' ? (item.error_message || item.message) : item.message;
      return `<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:10px;padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);">
        <div style="min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="color:${tone};font-size:11px;font-weight:700;text-transform:uppercase;">${item.status}</span>
            <span style="color:#94a3b8;font-size:10px;">${item.trigger}</span>
            <span style="color:#64748b;font-size:10px;">${meta}</span>
          </div>
          <div style="color:#e2e8f0;font-size:12px;margin-top:4px;">${msg || 'Sync update'}</div>
          <div style="color:#64748b;font-size:10px;margin-top:4px;">Rows: ${item.row_count || 0}</div>
        </div>
        <div>${retryBtn}</div>
      </div>`;
    }).join('');
  };

  const loadHistory = (connectorId) => {
    const item = connectorMap.get(String(connectorId));
    if (!item || !item.historyUrl) return;
    fetch(item.historyUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
      .then((r) => r.ok ? r.json() : null)
      .then((payload) => {
        if (!payload || !payload.ok || !payload.history) return;
        renderHistory(connectorId, payload.history.items || []);
      })
      .catch(() => {
        renderHistory(connectorId, []);
      });
  };

  const refreshAll = () => {
    fetch(cfg.summaryUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
      .then((r) => r.ok ? r.json() : null)
      .then((payload) => {
        if (!payload || !payload.ok) return;
        updateSummary(payload.summary);
        (payload.connectors || []).forEach(updateCard);
      })
      .catch(() => {});
  };

  document.addEventListener('click', (event) => {
    const toggle = event.target.closest('.connector-history-toggle');
    if (toggle) {
      const connectorId = String(toggle.getAttribute('data-connector-id') || '');
      const panel = document.getElementById(`connector-history-${connectorId}`);
      if (!panel) return;
      const hidden = panel.hasAttribute('hidden');
      if (hidden) {
        panel.removeAttribute('hidden');
        loadHistory(connectorId);
        toggle.textContent = 'Hide history';
      } else {
        panel.setAttribute('hidden', 'hidden');
        toggle.textContent = 'History';
      }
      return;
    }

    const refreshBtn = event.target.closest('[data-connector-history-refresh]');
    if (refreshBtn) {
      loadHistory(String(refreshBtn.getAttribute('data-connector-history-refresh') || ''));
      return;
    }

    const retryBtn = event.target.closest('[data-retry-log]');
    if (retryBtn && retryBaseUrl) {
      const logId = retryBtn.getAttribute('data-retry-log');
      const url = retryBaseUrl.replace(/0\/$/, `${logId}/`);
      retryBtn.disabled = true;
      fetch(url, { method: 'POST', headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '' }})
        .then(async (r) => ({ ok: r.ok, payload: await r.json().catch(() => null) }))
        .then(({ ok, payload }) => {
          if (payload && payload.connector) updateCard(payload.connector);
          if (payload && payload.history) renderHistory(payload.history.connector_id, payload.history.items || []);
          refreshAll();
        })
        .catch(() => {})
        .finally(() => { retryBtn.disabled = false; });
    }
  });

  refreshAll();
  if (cfg.pollMs > 0) window.setInterval(refreshAll, cfg.pollMs);
})();
