(function(){
  const configEl = document.getElementById('analysis-studio-config');
  if (!configEl) return;
  const cfg = JSON.parse(configEl.textContent);
  const overlay = document.getElementById('studio-inspector-overlay');
  const panel = document.getElementById('studio-inspector');
  const closeBtn = document.getElementById('close-inspector');
  const cancelBtn = document.getElementById('cancel-inspector');
  const saveBtn = document.getElementById('save-inspector');
  const statusEl = document.getElementById('inspector-status');
  const chartIdEl = document.getElementById('inspector-chart-id');
  let activeChartId = '';

  const fields = {
    title: document.getElementById('inspector-title'),
    chart_type: document.getElementById('inspector-chart-type'),
    aggregation: document.getElementById('inspector-aggregation'),
    color: document.getElementById('inspector-color'),
    x_axis: document.getElementById('inspector-x-axis'),
    y_axis: document.getElementById('inspector-y-axis'),
    size: document.getElementById('inspector-size'),
    rolling_window: document.getElementById('inspector-rolling-window'),
    top_n: document.getElementById('inspector-top-n'),
    comparison_mode: document.getElementById('inspector-comparison'),
    target_column: document.getElementById('inspector-target-column'),
    benchmark_column: document.getElementById('inspector-benchmark-column'),
    show_annotations: document.getElementById('inspector-annotations'),
  };

  function openInspector(card) {
    activeChartId = card.dataset.chartId;
    chartIdEl.textContent = `Chart ${activeChartId.slice(0, 8)}`;
    fields.title.value = card.dataset.title || '';
    fields.chart_type.value = card.dataset.chartType || 'bar';
    fields.aggregation.value = card.dataset.aggregation || 'sum';
    fields.color.value = card.dataset.color || 'violet';
    fields.x_axis.value = card.dataset.xAxis || '';
    fields.y_axis.value = card.dataset.yAxis || '';
    fields.size.value = card.dataset.size || 'md';
    fields.rolling_window.value = card.dataset.rollingWindow || 3;
    fields.top_n.value = card.dataset.topN || 10;
    fields.comparison_mode.value = card.dataset.comparisonMode || '';
    if (fields.target_column) fields.target_column.value = card.dataset.targetColumn || '';
    if (fields.benchmark_column) fields.benchmark_column.value = card.dataset.benchmarkColumn || '';
    fields.show_annotations.checked = card.dataset.showAnnotations === 'true';
    overlay.classList.remove('hidden');
    panel.classList.remove('translate-x-full');
    statusEl.textContent = 'Editing selected chart settings.';
  }

  function closeInspector() {
    overlay.classList.add('hidden');
    panel.classList.add('translate-x-full');
  }

  async function saveInspector() {
    if (!activeChartId) return;
    const payload = {
      title: fields.title.value,
      chart_type: fields.chart_type.value,
      aggregation: fields.aggregation.value,
      color: fields.color.value,
      x_axis: fields.x_axis.value,
      y_axis: fields.y_axis.value,
      size: fields.size.value,
      rolling_window: parseInt(fields.rolling_window.value || '3', 10),
      top_n: parseInt(fields.top_n.value || '10', 10),
      comparison_mode: fields.comparison_mode.value,
      target_column: fields.target_column ? fields.target_column.value : '',
      benchmark_column: fields.benchmark_column ? fields.benchmark_column.value : '',
      show_annotations: fields.show_annotations.checked,
    };
    const response = await fetch(`${cfg.chartUpdateBase}${activeChartId}/update/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': cfg.csrf,
      },
      body: JSON.stringify(payload),
    });
    const data = await response.json();
    if (!response.ok || !data.ok) {
      statusEl.textContent = data.error || 'Unable to save chart settings.';
      return;
    }
    const card = document.querySelector(`.studio-chart-card[data-chart-id="${activeChartId}"]`);
    if (card) {
      card.dataset.title = data.chart.title;
      card.dataset.chartType = data.chart.chart_type;
      card.dataset.aggregation = data.chart.aggregation;
      card.dataset.color = data.chart.color;
      card.dataset.xAxis = data.chart.x_axis;
      card.dataset.yAxis = data.chart.y_axis;
      card.dataset.size = data.chart.size;
      card.dataset.targetColumn = data.chart.config_json?.target_column || '';
      card.dataset.benchmarkColumn = data.chart.config_json?.benchmark_column || '';
      card.dataset.comparisonMode = data.chart.config_json?.comparison_mode || '';
      card.dataset.rollingWindow = data.chart.config_json?.rolling_window || 3;
      card.dataset.topN = data.chart.config_json?.top_n || 10;
      card.dataset.showAnnotations = data.chart.config_json?.show_annotations ? 'true' : 'false';
      const titleEl = card.querySelector('p.text-sm');
      if (titleEl) titleEl.textContent = data.chart.title;
      const axisEl = card.querySelector('p.text-xs');
      if (axisEl) axisEl.textContent = `${data.chart.x_axis || ''}${data.chart.x_axis && data.chart.y_axis ? ' → ' : ''}${data.chart.y_axis || ''}`;
    }
    statusEl.textContent = 'Chart settings saved and chart payload rebuilt.';
    closeInspector();
  }

  document.querySelectorAll('.studio-chart-card').forEach((card) => {
    card.addEventListener('click', () => openInspector(card));
  });

  overlay?.addEventListener('click', closeInspector);
  closeBtn?.addEventListener('click', closeInspector);
  cancelBtn?.addEventListener('click', closeInspector);
  saveBtn?.addEventListener('click', saveInspector);
})();
