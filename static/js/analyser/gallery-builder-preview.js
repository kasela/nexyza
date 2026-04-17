(function(){
  function ensureNs(){
    window.NexyzaGallery = window.NexyzaGallery || {};
    return window.NexyzaGallery;
  }
  var ns = ensureNs();

  ns.makeBuilderPreview = function makeBuilderPreview(ctx){
    function renderPreview(raw){
      var BP = ctx.BP;
      var canvas = document.getElementById('bp-canvas');
      var kpiView = document.getElementById('bp-kpi-view');
      var msg = document.getElementById('bp-preview-msg');
      if (BP.chartInst) { BP.chartInst.destroy(); BP.chartInst = null; }
      if (!canvas || !kpiView) return;
      if (raw.kpi) {
        canvas.style.display = 'none';
        kpiView.style.display = 'flex';
        if (msg) msg.style.display = 'none';
        var val = document.getElementById('bp-kpi-val');
        var lbl = document.getElementById('bp-kpi-lbl');
        if (val) val.textContent = raw.value || '—';
        if (lbl) lbl.textContent = raw.label || '';
        return;
      }
      kpiView.style.display = 'none';
      canvas.style.display = 'block';
      if (raw.error) {
        if (msg) { msg.style.display='flex'; msg.textContent=raw.error; msg.style.color='#f87171'; }
        canvas.style.display='none';
        return;
      }
      if (!raw.labels || !raw.labels.length) {
        if (msg) { msg.style.display='flex'; msg.textContent='Select X and Y axes to preview'; msg.style.color='#475569'; }
        canvas.style.display='none';
        return;
      }
      if (msg) msg.style.display='none';
      var ctype = raw.chart_type || 'bar';
      var isH = !!raw.is_horizontal;
      var jsType = ({area:'line', histogram:'bar', horizontal_bar:'bar'})[ctype] || ctype;
      var scales = {};
      if (jsType !== 'pie' && jsType !== 'doughnut') {
        scales = isH ? {
          x:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#64748b',font:{size:9}}},
          y:{grid:{color:'rgba(255,255,255,.03)'},ticks:{color:'#64748b',font:{size:9}}}
        } : {
          x:{grid:{color:'rgba(255,255,255,.03)'},ticks:{color:'#64748b',font:{size:9},maxTicksLimit:8}},
          y:{grid:{color:'rgba(255,255,255,.05)'},ticks:{color:'#64748b',font:{size:9}}}
        };
        if (raw.has_dual_axis && raw.y2_label && !isH) {
          scales.y2 = {position:'right',grid:{drawOnChartArea:false},ticks:{color:'#60a5fa',font:{size:9}}};
        }
      }
      Chart.defaults.color = '#94a3b8';
      Chart.defaults.font = {family:"'DM Sans',system-ui",size:10};
      BP.chartInst = new Chart(canvas,{type:isH?'bar':jsType,data:{labels:raw.labels,datasets:raw.datasets||[]},options:{indexAxis:isH?'y':'x',responsive:true,maintainAspectRatio:false,animation:{duration:200},plugins:{legend:{display:(raw.datasets||[]).length>1||jsType==='pie'||jsType==='doughnut',position:(jsType==='pie'||jsType==='doughnut')?'right':'top',labels:{color:'#94a3b8',font:{size:9},boxWidth:7,padding:5}}},scales:scales}});
    }

    function fetchPreview(){
      var BP = ctx.BP;
      var cfg = ctx.cfg;
      var CSRF = ctx.CSRF;
      var x = (document.getElementById('bp-x') || {}).value || '';
      var y = (document.getElementById('bp-y') || {}).value || '';
      if (!x && !y && BP.type !== 'kpi') return;
      var extras = Array.from(document.querySelectorAll('input[name="bp-extra"]:checked')).map(function(c){ return c.value; }).join(',');
      var spin = document.getElementById('bp-preview-spin');
      var msg = document.getElementById('bp-preview-msg');
      if (spin) spin.style.display = 'flex';
      if (msg) msg.style.display = 'none';
      var fd = new FormData();
      fd.append('csrfmiddlewaretoken', CSRF);
      fd.append('chart_type', BP.type);
      fd.append('x_axis', x);
      fd.append('y_axis', y);
      fd.append('aggregation', (document.getElementById('bp-agg') || {}).value || 'mean');
      fd.append('group_by', (document.getElementById('bp-group') || {}).value || '');
      fd.append('color', BP.color);
      fd.append('title', (document.getElementById('bp-title') || {}).value || 'Preview');
      fd.append('config_json_extra_measures', extras);
      fd.append('config_json_y2_axis', '');
      if (!cfg.previewUrl) {
        if (spin) spin.style.display = 'none';
        if (msg) { msg.style.display = 'flex'; msg.textContent = 'Preview endpoint unavailable'; }
        return;
      }
      fetch(cfg.previewUrl, { method:'POST', body:fd, headers:{'X-CSRFToken': CSRF, 'X-Requested-With':'XMLHttpRequest'} })
        .then(function(r){
          return r.json().then(function(payload){
            if (!r.ok) { throw payload || {error:'Preview failed'}; }
            return payload;
          });
        })
        .then(function(raw){ if (spin) spin.style.display = 'none'; renderPreview(raw); })
        .catch(function(err){
          if (spin) spin.style.display = 'none';
          if (msg) { msg.style.display = 'flex'; msg.textContent = (err && (err.message || err.error)) || 'Preview failed'; msg.style.color='#f87171'; }
        });
    }

    function triggerPreview(){
      ctx.builderState.persistBuilderState();
      clearTimeout(ctx.BP.debounce);
      ctx.BP.debounce = setTimeout(fetchPreview, 350);
    }

    return {
      renderPreview: renderPreview,
      fetchPreview: fetchPreview,
      triggerPreview: triggerPreview,
    };
  };
})();
