(function(){
  const button = document.getElementById('scenario-run');
  if (!button) return;
  button.addEventListener('click', async function(){
    const url = button.dataset.url;
    const csrf = button.dataset.csrf;
    const payload = {
      base_value: Number(button.dataset.baseValue || 0),
      growth_pct: Number(document.getElementById('scenario-growth')?.value || 0),
      cost_pct: Number(document.getElementById('scenario-cost')?.value || 0),
      target_override: document.getElementById('scenario-target')?.value || ''
    };
    const res = await fetch(url, {
      method: 'POST',
      headers: {'Content-Type':'application/json','X-CSRFToken': csrf},
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (!data.ok) return;
    const box = document.getElementById('scenario-result');
    if (!box) return;
    box.querySelector('[data-key="projected_value"]').textContent = data.scenario.projected_value;
    box.querySelector('[data-key="net_value"]').textContent = data.scenario.net_value;
    box.querySelector('[data-key="variance_to_target"]').textContent = data.scenario.variance_to_target ?? '—';
  });
})();
