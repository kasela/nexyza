
(function(){
  function readConfig(){
    var node = document.getElementById('result-page-config');
    if (!node) return null;
    try { return JSON.parse(node.textContent || node.innerText || '{}'); } catch (e) { return null; }
  }
  function init(){
    var cfg = readConfig();
    if (!cfg || !cfg.uploadId) return;
    var uploadId = cfg.uploadId;
    var tabOrder = cfg.tabOrder || ['charts','overview','columns','preview','correlation','ai','nlq','share'];
    var TAB_KEY = 'nexyza:active-tab:' + uploadId;
    var CHART_STATE_KEY = 'nexyza:chart-state:' + uploadId;

    function getVisibleChartCards(){
      return Array.prototype.slice.call(document.querySelectorAll('#charts-grid .chart-card-wrapper')).filter(function(el){
        return el.style.display !== 'none';
      });
    }
    function updateChartSummary(){
      var all = document.querySelectorAll('#charts-grid .chart-card-wrapper').length;
      var visible = getVisibleChartCards().length;
      var el = document.getElementById('charts-summary');
      if (el) el.textContent = 'Showing ' + visible + ' of ' + all + ' charts';
    }
    function persistChartState(){
      var activeTypeBtn = document.querySelector('#type-filters .tb-btn.active');
      var state = {
        search: (document.getElementById('chart-search') || {}).value || '',
        sort: (document.getElementById('chart-sort') || {}).value || 'default',
        layout: document.getElementById('layout-2') && document.getElementById('layout-2').classList.contains('active') ? 2 : 3,
        type: activeTypeBtn ? ((activeTypeBtn.textContent || '').trim()) : 'All'
      };
      try { localStorage.setItem(CHART_STATE_KEY, JSON.stringify(state)); } catch(e) {}
      updateChartSummary();
    }

    var originalShowTab = window.showTab;
    if (typeof originalShowTab === 'function') {
      window.showTab = function(name){
        originalShowTab(name);
        try { localStorage.setItem(TAB_KEY, name); } catch(e) {}
        if (history && history.replaceState) {
          var url = new URL(window.location.href);
          url.hash = 'tab=' + name;
          history.replaceState(null, '', url.toString());
        }
      };
    }

    var originalFilterCharts = window.filterCharts;
    if (typeof originalFilterCharts === 'function') {
      window.filterCharts = function(q){ originalFilterCharts(q); persistChartState(); };
    }
    var originalFilterByType = window.filterByType;
    if (typeof originalFilterByType === 'function') {
      window.filterByType = function(type, btn){ originalFilterByType(type, btn); persistChartState(); };
    }
    var originalSetLayout = window.setLayout;
    if (typeof originalSetLayout === 'function') {
      window.setLayout = function(n){ originalSetLayout(n); persistChartState(); };
    }

    window.sortCharts = function(mode){
      var grid = document.getElementById('charts-grid');
      if (!grid) return;
      var cards = Array.prototype.slice.call(grid.querySelectorAll('.chart-card-wrapper'));
      cards.sort(function(a,b){
        var at = (a.dataset.title || '').toLowerCase();
        var bt = (b.dataset.title || '').toLowerCase();
        var aty = (a.dataset.type || '').toLowerCase();
        var bty = (b.dataset.type || '').toLowerCase();
        if (mode === 'title-asc') return at.localeCompare(bt);
        if (mode === 'title-desc') return bt.localeCompare(at);
        if (mode === 'type') return (aty + at).localeCompare(bty + bt);
        return parseInt(a.dataset.order || '0', 10) - parseInt(b.dataset.order || '0', 10);
      });
      cards.forEach(function(card){ grid.appendChild(card); });
      persistChartState();
    };

    var originalPresentMode = typeof window.presentMode === 'function' ? window.presentMode : null;
    window.presentMode = function(mode){
      try { console.log('[NXPresent] result-enhancements intercept presentMode', {mode: mode}); } catch(e) {}
      if (typeof originalPresentMode === 'function') {
        originalPresentMode(mode || 'all');
      } else if (typeof window.presentAll === 'function') {
        window.presentAll();
      }
      if (typeof window.toggleMenu === 'function') window.toggleMenu('present-menu');
      setTimeout(function(){
        var badge = document.getElementById('nxp-badge');
        if (badge) badge.textContent = mode === 'charts' ? 'Charts only' : mode === 'kpis' ? 'KPIs only' : 'Presentation';
      }, 80);
    };

    function restoreState(){
      var wanted = null;
      try {
        if (window.location.hash && window.location.hash.indexOf('tab=') !== -1) wanted = window.location.hash.split('tab=')[1];
        if (!wanted) wanted = localStorage.getItem(TAB_KEY);
      } catch(e) {}
      if (wanted && document.getElementById('panel-' + wanted) && typeof window.showTab === 'function') window.showTab(wanted);

      try {
        var raw = localStorage.getItem(CHART_STATE_KEY);
        if (raw) {
          var state = JSON.parse(raw);
          if (state.search && document.getElementById('chart-search') && typeof originalFilterCharts === 'function') {
            document.getElementById('chart-search').value = state.search;
            originalFilterCharts(state.search);
          }
          if (state.layout && typeof originalSetLayout === 'function') originalSetLayout(state.layout);
          if (state.sort && document.getElementById('chart-sort')) {
            document.getElementById('chart-sort').value = state.sort;
            if (state.sort !== 'default') window.sortCharts(state.sort);
          }
          if (state.type) {
            Array.prototype.slice.call(document.querySelectorAll('#type-filters .tb-btn')).forEach(function(btn){
              if ((btn.textContent || '').trim().toLowerCase() === state.type.trim().toLowerCase()) btn.click();
            });
          }
        }
      } catch(e) {}
      updateChartSummary();
    }

    document.addEventListener('keydown', function(e){
      var tag = ((document.activeElement && document.activeElement.tagName) || '').toLowerCase();
      var editing = tag === 'input' || tag === 'textarea' || tag === 'select';
      if (!editing && e.key.toLowerCase() === 'p') { e.preventDefault(); window.presentMode('all'); }
      if (!editing && e.key === '/') {
        var search = document.getElementById('chart-search');
        if (search) { e.preventDefault(); search.focus(); search.select(); }
      }
      if (!editing && /^[1-7]$/.test(e.key)) {
        var idx = parseInt(e.key, 10) - 1;
        var tab = tabOrder[idx];
        if (tab && document.getElementById('panel-' + tab) && typeof window.showTab === 'function') {
          e.preventDefault();
          window.showTab(tab);
        }
      }
    });

    restoreState();
    window.addEventListener('load', updateChartSummary);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
