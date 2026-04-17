(function(){
  var cfgEl = document.getElementById('report-builder-config');
  if (!cfgEl) return;
  var cfg = {};
  try { cfg = JSON.parse(cfgEl.textContent || '{}'); } catch (e) { cfg = {}; }
  var api = window.NexyzaReportBuilder = window.NexyzaReportBuilder || {};
  api.cfg = cfg;
  api.REPORT_PK = cfg.reportPk || '';
  api.CSRF = cfg.csrfToken || '';
  api.STORAGE_KEY = 'nexyza-report-builder:' + api.REPORT_PK;
  api.post = function(url, fd, hx){
    var headers = {};
    if (hx) headers['HX-Request'] = 'true';
    return fetch(url, {method:'POST', body:fd, headers:headers});
  };
  api.setLastAction = function(text){
    var el = document.getElementById('report-last-action');
    if (el) el.textContent = text;
  };

  api.showError = function(message){
    api.setLastAction(message || 'Something went wrong');
    try { window.alert(message || 'Something went wrong'); } catch (e) {}
  };
  api.readError = function(resp){
    return resp.json().catch(function(){ return {}; }).then(function(payload){
      var msg = (payload && (payload.error || payload.message)) || 'Request failed';
      if (payload && payload.field_errors) {
        var firstKey = Object.keys(payload.field_errors)[0];
        if (firstKey && payload.field_errors[firstKey]) msg += ' — ' + payload.field_errors[firstKey];
      }
      return Promise.reject({payload: payload, message: msg, response: resp});
    });
  };
  api.updateSectionSummary = function(){
    var count = document.querySelectorAll('#sections-canvas > [id^="sec-"]').length;
    var el = document.getElementById('report-section-summary');
    if (el) el.textContent = count + ' section' + (count === 1 ? '' : 's');
  };
  api.filterSections = function(query){
    query = (query || '').toLowerCase().trim();
    document.querySelectorAll('#sections-canvas > [id^="sec-"]').forEach(function(sec){
      var txt = (sec.textContent || '').toLowerCase();
      sec.style.display = !query || txt.indexOf(query) !== -1 ? '' : 'none';
    });
  };
  api.persistState = function(){
    try {
      localStorage.setItem(api.STORAGE_KEY, JSON.stringify({
        title: (document.getElementById('report-title-input') || {}).value || '',
        chartSel: (document.getElementById('add-chart-sel') || {}).value || '',
        statsSel: (document.getElementById('add-stats-sel') || {}).value || '',
        aiSel: (document.getElementById('add-ai-sel') || {}).value || '',
        sectionSearch: (document.getElementById('report-section-search') || {}).value || ''
      }));
    } catch (e) {}
  };
  api.restoreState = function(){
    try {
      var raw = localStorage.getItem(api.STORAGE_KEY);
      if (!raw) return;
      var state = JSON.parse(raw);
      [['add-chart-sel','chartSel'],['add-stats-sel','statsSel'],['add-ai-sel','aiSel']].forEach(function(pair){
        var el = document.getElementById(pair[0]);
        if (el && state[pair[1]]) el.value = state[pair[1]];
      });
      var search = document.getElementById('report-section-search');
      if (search && state.sectionSearch) {
        search.value = state.sectionSearch;
        api.filterSections(state.sectionSearch);
      }
    } catch (e) {}
  };
  api.syncTitlePreview = function(){
    var title = (document.getElementById('report-title-input') || {}).value || 'Untitled Report';
    var display = document.getElementById('report-title-display');
    if (display) display.textContent = title;
  };
})();
