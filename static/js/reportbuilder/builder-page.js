(function(){
  var api = window.NexyzaReportBuilder = window.NexyzaReportBuilder || {};
  if (!api.cfg) return;
  document.addEventListener('DOMContentLoaded', function(){
    api.restoreState();
    api.updateSectionSummary();
    api.syncTitlePreview();
    var search = document.getElementById('report-section-search');
    if (search) search.addEventListener('input', function(){ api.filterSections(search.value); api.persistState(); });
    ['add-chart-sel','add-stats-sel','add-ai-sel','report-title-input'].forEach(function(id){
      var el = document.getElementById(id);
      if (el) el.addEventListener('change', api.persistState);
      if (el && id === 'report-title-input') el.addEventListener('input', api.syncTitlePreview);
    });
    document.addEventListener('keydown', function(e){
      var tag = (document.activeElement && document.activeElement.tagName || '').toLowerCase();
      var editing = ['input','textarea','select'].indexOf(tag) !== -1 || (document.activeElement && document.activeElement.isContentEditable);
      if (!editing && e.key === '/') {
        e.preventDefault();
        if (search) { search.focus(); search.select(); }
      }
      if (!editing && e.key.toLowerCase() === 's' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        if (window.saveReportMeta) window.saveReportMeta();
      }
    });
  });
})();
