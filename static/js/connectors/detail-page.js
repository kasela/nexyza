(function(){
  const cfgEl = document.getElementById('connector-detail-config');
  if (!cfgEl) return;
  let cfg = {};
  try { cfg = JSON.parse(cfgEl.textContent || '{}'); } catch (e) { return; }

  const form = document.getElementById('connector-history-filters');
  const list = document.getElementById('connector-history-detail-list');

  const escapeHtml = (v) => String(v || '').replace(/[&<>"']/g, (ch) => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));

  const itemHtml = (item) => {
    const tone = item.status === 'ok' ? '#34d399' : item.status === 'error' ? '#f87171' : '#fbbf24';
    const retryBtn = item.can_retry ? `<button type="button" data-retry-log="${item.id}" style="padding:6px 10px;border-radius:10px;border:1px solid rgba(239,68,68,.2);background:rgba(239,68,68,.08);color:#fca5a5;font-size:11px;cursor:pointer;">Retry</button>` : '';
    return `<div data-history-item="${item.id}" style="padding:14px;border-radius:16px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;">
        <div style="min-width:0;">
          <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">
            <span style="color:${tone};font-size:11px;font-weight:700;text-transform:uppercase;">${escapeHtml(item.status)}</span>
            <span style="color:#94a3b8;font-size:10px;">${escapeHtml(item.trigger)}</span>
            <span style="color:#64748b;font-size:10px;">${escapeHtml(item.completed_human || item.started_human || '')}</span>
            <span style="color:#64748b;font-size:10px;">Rows ${escapeHtml(item.row_count || 0)}</span>
          </div>
          <div style="color:#e2e8f0;font-size:13px;margin-top:6px;">${escapeHtml(item.message || 'Sync update')}</div>
          ${item.error_message ? `<div style="color:#fca5a5;font-size:11px;margin-top:6px;">${escapeHtml(item.error_message)}</div>` : ''}
          ${item.alerts && item.alerts.length ? `<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">${item.alerts.map((a)=>`<span style=\"padding:4px 8px;border-radius:999px;background:rgba(251,191,36,.10);border:1px solid rgba(251,191,36,.18);color:#fde68a;font-size:10px;\">⚠ ${escapeHtml(a.label || '')}</span>`).join('')}</div>` : ''}
        </div>
        ${retryBtn}
      </div>
      <div style="margin-top:10px;">
        <label style="display:block;color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:.08em;margin-bottom:6px;">Notes</label>
        <textarea data-note-input="${item.id}" rows="2" style="width:100%;padding:10px 12px;border-radius:12px;border:1px solid rgba(255,255,255,.08);background:rgba(15,23,42,.6);color:#e2e8f0;font-size:12px;resize:vertical;">${escapeHtml(item.notes || '')}</textarea>
        <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-top:8px;">
          <div data-note-status="${item.id}" style="color:#64748b;font-size:11px;">Add operational notes for this run.</div>
          <button type="button" data-save-note="${item.id}" style="padding:6px 10px;border-radius:10px;border:1px solid rgba(124,58,237,.2);background:rgba(124,58,237,.08);color:#c4b5fd;font-size:11px;cursor:pointer;">Save note</button>
        </div>
      </div>
    </div>`;
  };


  const warningsWrap = document.getElementById('connector-health-warnings');
  const healthPanel = document.getElementById('connector-health-panel');

  const renderHealth = (health) => {
    if (!healthPanel || !health) return;
    const cards = healthPanel.querySelectorAll('div[style*="background:rgba(255,255,255,.03)"]');
    if (cards[0]) cards[0].querySelectorAll('div')[1].textContent = `${health.success_rate}%`;
    if (cards[1]) cards[1].querySelectorAll('div')[1].textContent = `${health.row_delta_pct || 0}%`;
    if (cards[2]) {
      const driftNode = cards[2].querySelectorAll('div')[1];
      driftNode.textContent = health.schema_drift && health.schema_drift.summary ? health.schema_drift.summary : 'No schema drift detected';
      driftNode.style.color = health.schema_drift && health.schema_drift.has_changes ? '#fbbf24' : '#34d399';
    }
    if (warningsWrap) {
      const items = (health.warnings || []).map((warning) => {
        const tone = warning.tone === 'error' ? ['rgba(239,68,68,.08)','rgba(239,68,68,.18)','#fecaca'] : warning.tone === 'warn' ? ['rgba(251,191,36,.08)','rgba(251,191,36,.18)','#fde68a'] : ['rgba(59,130,246,.08)','rgba(59,130,246,.18)','#bfdbfe'];
        return `<div style="padding:8px 10px;border-radius:10px;background:${tone[0]};border:1px solid ${tone[1]};color:${tone[2]};font-size:11px;">${escapeHtml(warning.label || '')}</div>`;
      });
      warningsWrap.innerHTML = items.length ? items.join('') : '<div style="padding:8px 10px;border-radius:10px;background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.18);color:#bbf7d0;font-size:11px;">No active health warnings.</div>';
    }
  };

  const loadHealth = () => {
    if (!cfg.healthUrl) return;
    fetch(cfg.healthUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
      .then((r) => r.ok ? r.json() : null)
      .then((payload) => { if (payload && payload.ok && payload.health) renderHealth(payload.health); })
      .catch(() => {});
  };



  const alertsList = document.getElementById('connector-alert-rules-list');
  const alertForm = document.getElementById('connector-alert-rule-form');
  const alertErrors = document.getElementById('connector-alert-rule-errors');

  const renderRules = (items) => {
    if (!alertsList) return;
    if (!items || !items.length) {
      alertsList.innerHTML = '<div style="padding:12px;border-radius:12px;background:rgba(255,255,255,.02);border:1px dashed rgba(255,255,255,.08);color:#64748b;font-size:11px;">No alert rules yet.</div>';
      return;
    }
    alertsList.innerHTML = items.map((rule) => `<div data-alert-rule="${escapeHtml(rule.id)}" style="padding:10px 12px;border-radius:12px;background:rgba(255,255,255,.025);border:1px solid rgba(255,255,255,.06);display:flex;align-items:center;justify-content:space-between;gap:10px;">
      <div>
        <div style="color:#e2e8f0;font-size:12px;font-weight:600;">${escapeHtml(rule.rule_label || rule.rule_type || '')}</div>
        <div style="color:#94a3b8;font-size:11px;margin-top:4px;">${rule.threshold !== null && rule.threshold !== undefined && rule.threshold !== '' ? `Threshold ${escapeHtml(rule.threshold)}` : 'No threshold'} · ${escapeHtml(rule.action_label || 'No Action')}</div>
      </div>
      <button type="button" data-delete-alert-rule="${escapeHtml(rule.id)}" style="padding:6px 10px;border-radius:10px;border:1px solid rgba(239,68,68,.18);background:rgba(239,68,68,.08);color:#fca5a5;font-size:11px;cursor:pointer;">Delete</button>
    </div>`).join('');
  };

  const loadRules = () => {
    if (!cfg.alertsUrl) return;
    fetch(cfg.alertsUrl, { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
      .then((r) => r.ok ? r.json() : null)
      .then((payload) => { if (payload && payload.ok && payload.rules) renderRules(payload.rules.items || []); })
      .catch(() => {});
  };

  const renderHistory = (items) => {
    if (!list) return;
    if (!items || !items.length) {
      list.innerHTML = '<div style="padding:18px;border-radius:16px;background:rgba(255,255,255,.025);border:1px dashed rgba(255,255,255,.08);color:#64748b;font-size:12px;">No sync logs match the current filters.</div>';
      return;
    }
    list.innerHTML = items.map(itemHtml).join('');
  };

  const loadHistory = () => {
    if (!cfg.detailHistoryUrl || !form) return;
    const params = new URLSearchParams(new FormData(form));
    fetch(`${cfg.detailHistoryUrl}?${params.toString()}`, { headers: { 'X-Requested-With': 'XMLHttpRequest' }})
      .then((r) => r.ok ? r.json() : null)
      .then((payload) => { if (payload && payload.ok && payload.history) renderHistory(payload.history.items || []); })
      .catch(() => {});
  };

  alertForm && alertForm.addEventListener('submit', function(event){
    event.preventDefault();
    alertErrors && (alertErrors.textContent = '');
    const btn = alertForm.querySelector('button');
    btn && (btn.disabled = true);
    fetch(cfg.addAlertRuleUrl, {
      method: 'POST',
      headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
      body: new URLSearchParams(new FormData(alertForm)).toString(),
    })
      .then(async (r) => ({ ok: r.ok, payload: await r.json().catch(() => null) }))
      .then(({ ok, payload }) => {
        if (!ok || !payload || !payload.ok) {
          const errors = payload && payload.errors ? Object.values(payload.errors).join(' ') : 'Could not save alert rule.';
          alertErrors && (alertErrors.textContent = errors);
          return;
        }
        alertForm.reset();
        renderRules((payload.rules && payload.rules.items) || []);
      })
      .catch(() => { alertErrors && (alertErrors.textContent = 'Could not save alert rule.'); })
      .finally(() => { btn && (btn.disabled = false); });
  });

  form && form.addEventListener('submit', function(event){
    event.preventDefault();
    loadHistory();
    const params = new URLSearchParams(new FormData(form));
    history.replaceState(null, '', `${location.pathname}?${params.toString()}`);
  });

  document.addEventListener('click', (event) => {
    const retryBtn = event.target.closest('[data-retry-log]');
    if (retryBtn && cfg.retryBaseUrl) {
      const logId = retryBtn.getAttribute('data-retry-log');
      retryBtn.disabled = true;
      fetch(cfg.retryBaseUrl.replace(/0\/$/, `${logId}/`), {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '' },
      })
        .then((r) => r.json().catch(() => null))
        .then(() => { loadHistory(); loadHealth(); })
        .finally(() => { retryBtn.disabled = false; });
      return;
    }

    const deleteAlertBtn = event.target.closest('[data-delete-alert-rule]');
    if (deleteAlertBtn && cfg.deleteAlertRuleBaseUrl) {
      const ruleId = deleteAlertBtn.getAttribute('data-delete-alert-rule');
      deleteAlertBtn.disabled = true;
      fetch(cfg.deleteAlertRuleBaseUrl.replace('00000000-0000-0000-0000-000000000000', ruleId), {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '' },
      })
        .then(async (r) => ({ ok: r.ok, payload: await r.json().catch(() => null) }))
        .then(({ ok, payload }) => { if (ok && payload && payload.ok && payload.rules) renderRules(payload.rules.items || []); })
        .finally(() => { deleteAlertBtn.disabled = false; });
      return;
    }

    const saveBtn = event.target.closest('[data-save-note]');
    if (saveBtn && cfg.saveNoteBaseUrl) {
      const logId = saveBtn.getAttribute('data-save-note');
      const input = document.querySelector(`[data-note-input="${logId}"]`);
      const status = document.querySelector(`[data-note-status="${logId}"]`);
      saveBtn.disabled = true;
      status && (status.textContent = 'Saving…');
      const body = new URLSearchParams({ notes: input ? input.value : '' });
      fetch(cfg.saveNoteBaseUrl.replace(/0\/$/, `${logId}/`), {
        method: 'POST',
        headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': (document.querySelector('[name=csrfmiddlewaretoken]') || {}).value || '', 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' },
        body: body.toString(),
      })
        .then(async (r) => ({ ok: r.ok, payload: await r.json().catch(() => null) }))
        .then(({ ok, payload }) => {
          if (!ok || !payload || !payload.ok) {
            status && (status.textContent = (payload && payload.errors && payload.errors.notes) || 'Could not save note.');
            return;
          }
          status && (status.textContent = 'Saved');
        })
        .catch(() => { status && (status.textContent = 'Could not save note.'); })
        .finally(() => { saveBtn.disabled = false; });
    }
  });

  loadHealth();
  loadRules();
})();
