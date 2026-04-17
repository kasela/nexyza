(function(){
  function ensureNs(){
    window.NexyzaGallery = window.NexyzaGallery || {};
    return window.NexyzaGallery;
  }
  var ns = ensureNs();
  ns.safeText = ns.safeText || function(v){ return (v == null ? '' : String(v)); };

  ns.makeGalleryControls = function makeGalleryControls(ctx){
    function updateGallerySummary(){
      var all = document.querySelectorAll('#charts-grid .chart-card').length;
      var visible = Array.prototype.slice.call(document.querySelectorAll('#charts-grid .chart-card')).filter(function(el){
        return el.style.display !== 'none';
      }).length;
      var badge = document.getElementById('chart-count-badge');
      if (badge) badge.textContent = visible;
      var summary = document.getElementById('gallery-summary');
      if (summary) summary.textContent = 'Showing ' + visible + ' of ' + all + ' charts';
      var empty = document.getElementById('gallery-empty-state');
      if (empty) empty.style.display = visible ? 'none' : 'flex';
    }

    function matchesType(type, filter, card){
      if (!filter || filter === 'all') return true;
      if (filter === 'line') return type === 'line' || type === 'area';
      if (filter === 'bar') return type === 'bar' || type === 'horizontal_bar';
      if (filter === 'doughnut') return type === 'doughnut' || type === 'pie';
      if (filter === 'auto') return ns.safeText(card.dataset.auto) === 'true';
      return type === filter;
    }

    function persistGalleryState(){
      var activeBtn = document.querySelector('.filter-pill.active[data-filter]');
      var state = {
        search: (document.getElementById('chart-search') || {}).value || '',
        filter: activeBtn ? activeBtn.getAttribute('data-filter') : 'all',
        sort: (document.getElementById('gallery-sort') || {}).value || 'manual',
        layout: document.getElementById('layout-2') && document.getElementById('layout-2').classList.contains('active') ? 2 : 3,
      };
      try { localStorage.setItem(ctx.STATE_KEY, JSON.stringify(state)); } catch (e) {}
      updateGallerySummary();
    }

    function filterCharts(q){
      q = ns.safeText(q).toLowerCase();
      document.querySelectorAll('#charts-grid .chart-card').forEach(function(card){
        var title = ns.safeText(card.dataset.title).toLowerCase();
        var passesSearch = !q || title.indexOf(q) !== -1;
        var active = document.querySelector('.filter-pill.active[data-filter]');
        var activeType = active ? active.getAttribute('data-filter') : 'all';
        var type = ns.safeText(card.dataset.type).toLowerCase();
        var passesType = matchesType(type, activeType, card);
        card.style.display = (passesSearch && passesType) ? '' : 'none';
      });
      persistGalleryState();
    }

    function filterType(type, btn){
      document.querySelectorAll('.filter-pill[data-filter]').forEach(function(b){ b.classList.remove('active'); });
      if (btn) btn.classList.add('active');
      filterCharts((document.getElementById('chart-search') || {}).value || '');
    }

    function setLayout(n){
      var grid = document.getElementById('charts-grid');
      if (grid) grid.style.gridTemplateColumns = 'repeat(' + n + ',minmax(0,1fr))';
      ['2','3'].forEach(function(x){
        var btn = document.getElementById('layout-' + x);
        if (btn) btn.classList.toggle('active', String(x) === String(n));
      });
      persistGalleryState();
    }

    function sortGallery(mode){
      var grid = document.getElementById('charts-grid');
      if (!grid) return;
      var cards = Array.prototype.slice.call(grid.querySelectorAll('.chart-card'));
      cards.sort(function(a,b){
        var at = ns.safeText(a.dataset.title).toLowerCase();
        var bt = ns.safeText(b.dataset.title).toLowerCase();
        var aty = ns.safeText(a.dataset.type).toLowerCase();
        var bty = ns.safeText(b.dataset.type).toLowerCase();
        var asz = ns.safeText(a.dataset.size);
        var bsz = ns.safeText(b.dataset.size);
        var orderWeight = {sm:1, md:2, lg:3, full:4};
        if (mode === 'title-asc') return at.localeCompare(bt);
        if (mode === 'title-desc') return bt.localeCompare(at);
        if (mode === 'type') return (aty + at).localeCompare(bty + bt);
        if (mode === 'largest') return (orderWeight[bsz] || 0) - (orderWeight[asz] || 0) || at.localeCompare(bt);
        if (mode === 'auto-first') return (ns.safeText(b.dataset.auto) === 'true') - (ns.safeText(a.dataset.auto) === 'true') || at.localeCompare(bt);
        return parseInt(a.dataset.order || '0', 10) - parseInt(b.dataset.order || '0', 10);
      });
      cards.forEach(function(card){ grid.appendChild(card); });
      persistGalleryState();
    }

    function initSortable(){
      var grid = document.getElementById('charts-grid');
      if (!grid || typeof Sortable === 'undefined') return;
      if (grid._sortable) grid._sortable.destroy();
      grid._sortable = Sortable.create(grid, {
        animation:200, ghostClass:'opacity-30', handle:'.drag-handle',
        onEnd:function(){
          var order = Array.prototype.slice.call(grid.querySelectorAll('.chart-card')).map(function(el){ return el.dataset.id; });
          fetch(ctx.cfg.reorderUrl, { method:'POST', headers:{'Content-Type':'application/json','X-CSRFToken':ctx.CSRF}, body:JSON.stringify({order:order}) });
        }
      });
    }

    function restoreGalleryState(){
      try {
        var raw = localStorage.getItem(ctx.STATE_KEY);
        if (!raw) { updateGallerySummary(); return; }
        var state = JSON.parse(raw);
        if (state.search && document.getElementById('chart-search')) document.getElementById('chart-search').value = state.search;
        if (state.layout) setLayout(state.layout);
        if (state.sort && document.getElementById('gallery-sort')) {
          document.getElementById('gallery-sort').value = state.sort;
          sortGallery(state.sort);
        }
        var activeBtn = document.querySelector('.filter-pill[data-filter="' + (state.filter || 'all') + '"]');
        if (activeBtn) filterType(state.filter, activeBtn);
        else filterCharts((document.getElementById('chart-search') || {}).value || '');
      } catch (e) {
        updateGallerySummary();
      }
    }

    function bindKeyboardShortcuts(){
      document.addEventListener('keydown', function(e){
        var tag = ((document.activeElement && document.activeElement.tagName) || '').toLowerCase();
        var editing = tag === 'input' || tag === 'textarea' || tag === 'select';
        if (!editing && e.key === '/') {
          var search = document.getElementById('chart-search');
          if (search) { e.preventDefault(); search.focus(); search.select(); }
        }
        if (editing) return;
        var map = {g:'all', k:'kpi', b:'bar', t:'line', h:'heatmap', a:'auto'};
        var key = e.key.toLowerCase();
        if (map[key]) {
          var btn = document.querySelector('.filter-pill[data-filter="' + map[key] + '"]');
          if (btn) { e.preventDefault(); btn.click(); }
        }
        if (key === 'p') {
          var back = document.querySelector('a[href*="/workspace/"]');
          if (back) window.location.href = back.getAttribute('href');
        }
      });
    }

    function bindLiveRefresh(){
      ctx.cfg.liveRefreshMs = (ctx.cfg.liveRefreshMinutes || 0) * 60000;
      if (ctx.cfg.liveRefreshMs && ctx.cfg.regenUrl) {
        var badge = document.createElement('div');
        badge.style.cssText = 'position:fixed;bottom:20px;right:20px;background:rgba(16,185,129,.15);border:1px solid rgba(16,185,129,.3);border-radius:10px;padding:8px 14px;font-size:12px;color:#34d399;z-index:100;display:flex;align-items:center;gap:8px;';
        badge.innerHTML = '<span style="width:7px;height:7px;background:#34d399;border-radius:50%;animation:pulse 2s infinite;"></span>Live·refreshes in<span id="rc"></span>';
        document.body.appendChild(badge);
        var secs = ctx.cfg.liveRefreshMs / 1000;
        setInterval(function(){
          secs -= 1;
          var m = Math.floor(secs/60), s = secs%60;
          var rc = document.getElementById('rc');
          if (rc) rc.textContent = m > 0 ? m + 'm ' + s + 's' : s + 's';
          if (secs <= 0) {
            secs = ctx.cfg.liveRefreshMs / 1000;
            htmx.ajax('POST', ctx.cfg.regenUrl, '#charts-container');
          }
        }, 1000);
      }
    }

    return {
      updateGallerySummary:updateGallerySummary,
      persistGalleryState:persistGalleryState,
      filterCharts:filterCharts,
      filterType:filterType,
      setLayout:setLayout,
      sortGallery:sortGallery,
      initSortable:initSortable,
      restoreGalleryState:restoreGalleryState,
      bindKeyboardShortcuts:bindKeyboardShortcuts,
      bindLiveRefresh:bindLiveRefresh,
    };
  };
})();
