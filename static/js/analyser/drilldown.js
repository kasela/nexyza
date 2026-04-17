(function(){
  const configEl = document.getElementById('analysis-studio-config');
  if (!configEl) return;
  const cfg = JSON.parse(configEl.textContent);
  const dimensionEl = document.getElementById('drilldown-dimension');
  const metricEl = document.getElementById('drilldown-metric');
  const trigger = document.getElementById('run-drilldown');
  const summaryEl = document.getElementById('drilldown-summary');
  const barsEl = document.getElementById('drilldown-bars');

  function currentParent() {
    const filterState = window.AnalysisStudioState?.filterState || {};
    return {
      parent_dimension: filterState.dimension || '',
      parent_value: filterState.value || '',
    };
  }

  async function runDrilldown() {
    const payload = {
      dimension: dimensionEl?.value || '',
      metric: metricEl?.value || '',
      aggregation: 'sum',
      limit: 10,
      ...currentParent(),
    };
    const response = await fetch(cfg.drilldownUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': cfg.csrf,
      },
      body: JSON.stringify(payload),
    });
    if (!response.ok) return;
    const data = await response.json();
    summaryEl.textContent = data.summary || 'No drill-down result available.';
    barsEl.innerHTML = '';
    (data.labels || []).forEach((label, idx) => {
      const value = data.values?.[idx] ?? 0;
      const max = Math.max(...(data.values || [1]));
      const width = max ? Math.max(8, (value / max) * 100) : 8;
      const row = document.createElement('div');
      row.innerHTML = `
        <div class="flex items-center justify-between text-xs text-slate-300 mb-1"><span>${label}</span><span>${Number(value).toLocaleString()}</span></div>
        <div class="h-2 rounded-full bg-white/5 overflow-hidden"><div class="h-full rounded-full" style="width:${width}%;background:linear-gradient(90deg,rgba(124,58,237,.65),rgba(59,130,246,.65));"></div></div>
      `;
      row.className = 'rounded-xl p-2 bg-white/5 border border-white/10';
      barsEl.appendChild(row);
    });
    window.AnalysisStudioState = window.AnalysisStudioState || {};
    window.AnalysisStudioState.drillState = {
      dimension: payload.dimension,
      metric: payload.metric,
      parent_dimension: payload.parent_dimension,
      parent_value: payload.parent_value,
    };
    window.AnalysisStudioState.selectedMetric = payload.metric;
  }

  trigger?.addEventListener('click', runDrilldown);
})();
