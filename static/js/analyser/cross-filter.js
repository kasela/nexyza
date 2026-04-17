(function(){
  const configEl = document.getElementById('analysis-studio-config');
  if (!configEl) return;
  const cfg = JSON.parse(configEl.textContent);

  const els = {
    dimension: document.getElementById('studio-dimension'),
    value: document.getElementById('studio-value'),
    comparison: document.getElementById('studio-comparison'),
    topN: document.getElementById('studio-top-n'),
    apply: document.getElementById('studio-apply-filter'),
    clear: document.getElementById('studio-clear-filter'),
    rowsBefore: document.getElementById('studio-rows-before'),
    rowsAfter: document.getElementById('studio-rows-after'),
    primaryMetric: document.getElementById('studio-primary-metric'),
    primaryValue: document.getElementById('studio-primary-value'),
    activeFilter: document.getElementById('studio-active-filter'),
    topLabels: document.getElementById('studio-top-labels'),
    chartCards: document.querySelectorAll('.studio-chart-card'),
    saveView: document.getElementById('save-current-view'),
    savedList: document.getElementById('saved-views-list'),
  };

  function state() {
    return {
      dimension: els.dimension?.value || '',
      value: els.value?.value || '',
      comparison_mode: els.comparison?.value || '',
      top_n: parseInt(els.topN?.value || '10', 10),
    };
  }

  function csrfHeaders() {
    return {
      'Content-Type': 'application/json',
      'X-CSRFToken': cfg.csrf,
    };
  }

  function updateSummary(data) {
    const summary = data.summary || {};
    if (els.rowsBefore) els.rowsBefore.textContent = summary.rows_before ?? '—';
    if (els.rowsAfter) els.rowsAfter.textContent = summary.rows_after ?? '—';
    if (els.primaryMetric) els.primaryMetric.textContent = summary.primary_metric || 'Row count';
    if (els.primaryValue) els.primaryValue.textContent = summary.primary_value ?? '—';
    const filterLabel = data.state?.dimension && data.state?.value ? `${data.state.dimension}: ${data.state.value}` : 'None';
    if (els.activeFilter) els.activeFilter.textContent = filterLabel;
    if (els.topLabels) els.topLabels.textContent = (summary.top_labels || []).join(', ') || 'No notable groups yet.';

    const activeIds = new Set(data.impacted_chart_ids || []);
    els.chartCards.forEach((card) => {
      const isActive = activeIds.size && activeIds.has(card.dataset.chartId);
      card.style.borderColor = isActive ? 'rgba(124,58,237,.45)' : 'rgba(255,255,255,.06)';
      card.style.boxShadow = isActive ? '0 0 0 1px rgba(124,58,237,.12), 0 10px 30px rgba(124,58,237,.14)' : 'none';
    });
  }

  async function applyFilter() {
    const response = await fetch(cfg.crossFilterUrl, {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify(state()),
    });
    if (!response.ok) return;
    const data = await response.json();
    updateSummary(data);
    window.AnalysisStudioState = window.AnalysisStudioState || {};
    window.AnalysisStudioState.filterState = data.state;
  }

  function clearFilter() {
    if (els.dimension) els.dimension.value = '';
    if (els.value) els.value.value = '';
    if (els.comparison) els.comparison.value = '';
    if (els.topN) els.topN.value = '10';
    applyFilter();
  }

  async function saveCurrentView() {
    const title = window.prompt('Save analysis view as:', 'Phase 2 View');
    if (!title) return;
    const payload = {
      title,
      filters: state(),
      chart_order: Array.from(els.chartCards).map((card) => card.dataset.chartId),
      comparison_mode: els.comparison?.value || '',
      layout: { section: 'analysis_studio_phase2' },
      drill_state: window.AnalysisStudioState?.drillState || {},
      selected_metrics: [window.AnalysisStudioState?.selectedMetric || ''],
    };
    const response = await fetch(cfg.saveViewUrl, {
      method: 'POST',
      headers: csrfHeaders(),
      body: JSON.stringify(payload),
    });
    if (!response.ok) return;
    const data = await response.json();
    renderSavedViewItem(data.view);
  }

  function renderSavedViewItem(view) {
    if (!els.savedList) return;
    const empty = document.getElementById('saved-views-empty');
    if (empty) empty.remove();
    const existing = els.savedList.querySelector(`[data-view-id="${view.id}"]`);
    if (existing) existing.remove();
    const item = document.createElement('div');
    item.className = 'rounded-xl px-3 py-2 bg-white/5 border border-white/10 flex items-center justify-between gap-2 saved-view-item';
    item.dataset.viewId = view.id;
    item.innerHTML = `
      <button type="button" class="text-left flex-1 min-w-0 load-saved-view">
        <p class="text-sm text-slate-200 truncate">${view.title}</p>
        <p class="text-[11px] text-slate-500">${view.comparison_mode || 'No comparison'}</p>
      </button>
      ${view.is_default ? '<span class="text-[10px] uppercase tracking-wide text-violet-300">default</span>' : ''}
      <button type="button" class="text-rose-300 text-xs delete-saved-view">Delete</button>
    `;
    els.savedList.prepend(item);
  }

  async function loadView(id) {
    const response = await fetch(`${cfg.loadViewBase}${id}/`);
    if (!response.ok) return;
    const data = await response.json();
    const view = data.view || {};
    if (els.dimension) els.dimension.value = view.filters?.dimension || '';
    if (els.value) els.value.value = view.filters?.value || '';
    if (els.comparison) els.comparison.value = view.comparison_mode || view.filters?.comparison_mode || '';
    if (els.topN) els.topN.value = view.filters?.top_n || 10;
    window.AnalysisStudioState = window.AnalysisStudioState || {};
    window.AnalysisStudioState.drillState = view.drill_state || {};
    applyFilter();
  }

  async function deleteView(id, row) {
    const response = await fetch(`${cfg.loadViewBase}${id}/delete/`, { method: 'POST', headers: { 'X-CSRFToken': cfg.csrf } });
    if (!response.ok) return;
    row?.remove();
    if (!els.savedList.children.length) {
      els.savedList.innerHTML = '<p class="text-sm text-slate-400" id="saved-views-empty">No saved analysis views yet.</p>';
    }
  }

  document.addEventListener('click', (event) => {
    const loadBtn = event.target.closest('.load-saved-view');
    if (loadBtn) {
      const row = loadBtn.closest('.saved-view-item');
      if (row) loadView(row.dataset.viewId);
    }
    const deleteBtn = event.target.closest('.delete-saved-view');
    if (deleteBtn) {
      const row = deleteBtn.closest('.saved-view-item');
      if (row && window.confirm('Delete this saved analysis view?')) deleteView(row.dataset.viewId, row);
    }
  });

  els.apply?.addEventListener('click', applyFilter);
  els.clear?.addEventListener('click', clearFilter);
  els.saveView?.addEventListener('click', saveCurrentView);
  applyFilter();
})();
