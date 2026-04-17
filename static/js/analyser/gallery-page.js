(function(){
  window.NexyzaGallery = window.NexyzaGallery || {};
  var ns = window.NexyzaGallery;

  function init(){
    if (document.body && document.body.dataset.galleryModulesInit === '1') return;
    if (document.body) document.body.dataset.galleryModulesInit = '1';
    var cfg = ns.readConfig ? ns.readConfig() : null;
    if (!cfg || !cfg.uploadId) return;
    var ctx = {
      cfg: cfg,
      UPLOAD_ID: cfg.uploadId,
      CSRF: cfg.csrf || '',
      STATE_KEY: 'nexyza:gallery-state:' + cfg.uploadId,
      BUILDER_KEY: 'nexyza:gallery-builder:' + cfg.uploadId,
      BP: { type:'bar', color:'violet', chartInst:null, debounce:null }
    };

    ctx.builderState = ns.makeBuilderState(ctx);
    ctx.preview = ns.makeBuilderPreview(ctx);
    ctx.controls = ns.makeGalleryControls(ctx);

    window.openBuilder = function(){
      ctx.builderState.restoreBuilderState();
      ctx.builderState.bindBuilderPersistence();
      var panel = document.getElementById('builder-panel');
      var overlay = document.getElementById('bp-overlay');
      if (panel) panel.classList.add('open');
      if (overlay) overlay.classList.add('open');
      document.body.style.overflow = 'hidden';
    };
    window.closeBuilder = function(){
      var panel = document.getElementById('builder-panel');
      var overlay = document.getElementById('bp-overlay');
      if (panel) panel.classList.remove('open');
      if (overlay) overlay.classList.remove('open');
      document.body.style.overflow = '';
    };
    window.switchBpTab = function(t){
      ['build','quick'].forEach(function(n){
        var tab = document.getElementById('bptab-'+n);
        var panel = document.getElementById('bp-'+n+'-tab');
        if (tab) tab.classList.toggle('active', n===t);
        if (panel) panel.style.display = n===t ? 'flex' : 'none';
      });
    };
    window.selectType = function(t){
      ctx.BP.type = t;
      document.querySelectorAll('.ctype-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.type === t); });
      ctx.builderState.persistBuilderState();
      ctx.preview.triggerPreview();
    };
    window.selectColor = function(c){
      ctx.BP.color = c;
      document.querySelectorAll('.color-swatch').forEach(function(s){ s.classList.toggle('active', s.dataset.color === c); });
      ctx.builderState.persistBuilderState();
      ctx.preview.triggerPreview();
    };
    window.triggerPreview = ctx.preview.triggerPreview;
    window.filterCharts = ctx.controls.filterCharts;
    window.filterType = ctx.controls.filterType;
    window.setLayout = ctx.controls.setLayout;
    window.sortGallery = ctx.controls.sortGallery;
    window.initSortable = ctx.controls.initSortable;

    window.saveBuilderChart = function(){
      var btn = document.getElementById('bp-save-btn');
      if (btn) { btn.textContent = 'Saving…'; btn.disabled = true; }
      var extras = Array.from(document.querySelectorAll('input[name="bp-extra"]:checked')).map(function(c){return c.value;}).join(',');
      var titleInput = document.getElementById('bp-title');
      var title = titleInput ? titleInput.value.trim() : '';
      if (!title) {
        var x = (document.getElementById('bp-x') || {}).value || '';
        var y = (document.getElementById('bp-y') || {}).value || '';
        title = (y || 'Chart') + (x ? ' by ' + x : '');
      }
      var fd = new FormData();
      fd.append('csrfmiddlewaretoken', ctx.CSRF);
      fd.append('title', title);
      fd.append('chart_type', ctx.BP.type);
      fd.append('x_axis', (document.getElementById('bp-x') || {}).value || '');
      fd.append('y_axis', (document.getElementById('bp-y') || {}).value || '');
      fd.append('aggregation', (document.getElementById('bp-agg') || {}).value || 'mean');
      fd.append('group_by', (document.getElementById('bp-group') || {}).value || '');
      fd.append('color', ctx.BP.color);
      fd.append('size', (document.getElementById('bp-size') || {}).value || 'md');
      fd.append('config_json_extra_measures', extras);
      fd.append('config_json_x_label', (document.getElementById('bp-xlabel') || {}).value || '');
      fd.append('config_json_y_label', (document.getElementById('bp-ylabel') || {}).value || '');
      fd.append('config_json_insight', (document.getElementById('bp-insight') || {}).value || '');
      ctx.builderState.persistBuilderState();
      fetch(ctx.cfg.createUrl, { method:'POST', body:fd, headers:{'HX-Request':'true','X-CSRFToken':ctx.CSRF,'X-Requested-With':'XMLHttpRequest'} })
        .then(function(r){
          var ctype = r.headers.get('content-type') || '';
          if (ctype.indexOf('application/json') !== -1) {
            return r.json().then(function(payload){
              if (!r.ok) throw payload;
              return payload;
            });
          }
          return r.text().then(function(html){
            if (!r.ok) throw {error:'Could not save chart.'};
            return {html: html};
          });
        })
        .then(function(result){
          if (btn) { btn.textContent='+ Add to Gallery'; btn.disabled=false; }
          if (result && result.html) {
            var container = document.getElementById('charts-container');
            if (container) container.innerHTML = result.html;
            window.closeBuilder();
            ctx.controls.initSortable();
            ctx.controls.updateGallerySummary();
            ctx.controls.restoreGalleryState();
          }
        })
        .catch(function(err){
          if (btn) { btn.textContent='+ Add to Gallery'; btn.disabled=false; }
          var msg = document.getElementById('bp-preview-msg');
          if (msg) {
            msg.style.display = 'flex';
            msg.style.color = '#f87171';
            msg.textContent = (err && (err.message || err.error)) || 'Could not save chart.';
          }
        });
    };

    window.quickAdd = function(type, colName){
      var x = '', y = '';
      if (type === 'kpi' || type === 'histogram') y = colName;
      else {
        y = colName;
        if (ctx.cfg.firstCategory) x = ctx.cfg.firstCategory;
      }
      var suffixMap = {bar:'by ' + x, line:'Trend', kpi:'Total', histogram:'Distribution', doughnut:'Share', pie:'Share', horizontal_bar:'Breakdown'};
      var title = (colName + ' ' + (suffixMap[type] || '')).trim();
      var fd = new FormData();
      fd.append('csrfmiddlewaretoken', ctx.CSRF);
      fd.append('title', title);
      fd.append('chart_type', type);
      fd.append('x_axis', x);
      fd.append('y_axis', y);
      fd.append('aggregation','mean');
      fd.append('color','violet');
      fd.append('size','md');
      ctx.builderState.persistBuilderState();
      fetch(ctx.cfg.createUrl, { method:'POST', body:fd, headers:{'HX-Request':'true','X-CSRFToken':ctx.CSRF,'X-Requested-With':'XMLHttpRequest'} })
        .then(function(r){
          var ctype = r.headers.get('content-type') || '';
          if (ctype.indexOf('application/json') !== -1) {
            return r.json().then(function(payload){ if (!r.ok) throw payload; return payload; });
          }
          return r.text().then(function(html){ if (!r.ok) throw {error:'Could not create quick chart.'}; return {html: html}; });
        })
        .then(function(result){
          var container = document.getElementById('charts-container');
          if (container && result && result.html) container.innerHTML = result.html;
          ctx.controls.initSortable();
          ctx.controls.updateGallerySummary();
          ctx.controls.restoreGalleryState();
        })
        .catch(function(err){
          var msg = document.getElementById('bp-preview-msg');
          if (msg) {
            msg.style.display='flex';
            msg.style.color='#f87171';
            msg.textContent=(err && (err.message || err.error)) || 'Could not create quick chart.';
          }
        });
    };

    ctx.controls.bindKeyboardShortcuts();
    document.addEventListener('DOMContentLoaded', function(){
      ctx.controls.initSortable();
      ctx.controls.restoreGalleryState();
      ctx.builderState.restoreBuilderState();
      ctx.builderState.bindBuilderPersistence();
    });
    document.addEventListener('htmx:afterSwap', function(){
      ctx.controls.initSortable();
      ctx.controls.restoreGalleryState();
      ctx.builderState.bindBuilderPersistence();
    });
    ctx.controls.initSortable();
    ctx.controls.restoreGalleryState();
    ctx.builderState.restoreBuilderState();
    ctx.builderState.bindBuilderPersistence();
    ctx.controls.bindLiveRefresh();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
