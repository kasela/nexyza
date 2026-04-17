(function(){
  var api = window.NexyzaReportBuilder = window.NexyzaReportBuilder || {};
  if (!api.cfg) return;
  function addSection(fd, label){
    var empty = document.getElementById('empty-msg');
    if (empty) empty.remove();
    fd.append('csrfmiddlewaretoken', api.CSRF);
    api.post(api.cfg.addSectionUrl, fd, true)
      .then(function(r){ if (!r.ok) return api.readError(r); return r.text(); })
      .then(function(html){
        document.getElementById('sections-canvas').insertAdjacentHTML('beforeend', html);
        api.updateSectionSummary();
        api.filterSections((document.getElementById('report-section-search') || {}).value || '');
        api.persistState();
        api.setLastAction((label || 'Section') + ' added');
      })
      .catch(function(err){ api.showError((err && err.message) || 'Could not add section'); });
  }
  window.quickAddSection = function(type){ var fd = new FormData(); fd.append('section_type', type); addSection(fd, type.replace('_',' ')); };
  window.addChartSection = function(){ var sel = document.getElementById('add-chart-sel'); if (!sel || !sel.value) { alert('Select a chart first'); return; } var fd = new FormData(); fd.append('section_type','chart'); fd.append('chart_id', sel.value); addSection(fd, 'Chart'); };
  window.addDataSection = function(type){ var selId = type === 'stats' ? 'add-stats-sel' : 'add-ai-sel'; var sel = document.getElementById(selId); if (!sel || !sel.value) { alert('Select a dataset first'); return; } var fd = new FormData(); fd.append('section_type', type); fd.append('upload_id', sel.value); addSection(fd, type === 'stats' ? 'Stats' : 'AI insights'); };
  window.applySectionBundle = function(kind){
    var bundles = { executive: [['heading',{text:'Executive Summary'}],['text',{text:'Summarise the most important performance changes, trends, and management actions here.'}],['divider',{}]], story: [['heading',{text:'Performance Story'}],['text',{text:'Use this flow to explain the trend, highlight the chart, then close with a short recommendation.'}]] };
    (bundles[kind] || []).forEach(function(item, idx){ setTimeout(function(){ var fd = new FormData(); fd.append('section_type', item[0]); Object.keys(item[1]).forEach(function(k){ fd.append(k, item[1][k]); }); addSection(fd, item[0]); }, idx * 120); });
  };
  window.deleteSection = function(id){ if (!confirm('Remove this section?')) return; fetch(api.cfg.deleteSectionBase + id + '/delete/', {method:'POST', headers:{'X-CSRFToken':api.CSRF,'HX-Request':'true'}}).then(function(r){ if (!r.ok) return api.readError(r); var ct = (r.headers.get('content-type') || '').toLowerCase(); return ct.indexOf('application/json') !== -1 ? r.json() : {}; }).then(function(){ var el = document.getElementById('sec-' + id); if (el) el.remove(); api.updateSectionSummary(); api.setLastAction('Section removed'); }).catch(function(err){ api.showError((err && err.message) || 'Could not remove section'); }); };
  window.saveSectionText = function(id, text){ var fd = new FormData(); fd.append('csrfmiddlewaretoken', api.CSRF); fd.append('text', text); fetch(api.cfg.updateSectionBase + id + '/update/', {method:'POST', body:fd}).then(function(r){ if (!r.ok) return api.readError(r); return r.json(); }).then(function(){ api.setLastAction('Section content saved'); }).catch(function(err){ api.showError((err && err.message) || 'Could not save section content'); }); };
  window.clearSectionFilter = function(){ var search = document.getElementById('report-section-search'); if (search) search.value = ''; api.filterSections(''); api.persistState(); api.setLastAction('Section filter cleared'); };
  window.saveReportMeta = function(){ var title = (document.getElementById('report-title-input') || {}).value || ''; api.syncTitlePreview(); api.persistState(); var fd = new FormData(); fd.append('csrfmiddlewaretoken', api.CSRF); fd.append('title', title); api.post(api.cfg.metaUrl, fd).then(function(){ api.setLastAction('Saved report title'); }); };
  window.togglePublic = function(){ var fd = new FormData(); fd.append('csrfmiddlewaretoken', api.CSRF); fetch(api.cfg.togglePublicUrl, {method:'POST', body:fd}).then(function(r){ return r.json(); }).then(function(d){ var btn = document.getElementById('share-btn'); if (!btn) return; if(d.is_public){ btn.textContent = '🔓 Public'; btn.style.color = '#34d399'; btn.style.borderColor = 'rgba(16,185,129,.3)'; btn.style.background = 'rgba(16,185,129,.1)'; api.setLastAction('Public link enabled'); if(d.token) prompt('Public link (copy this):', window.location.origin + api.cfg.publicBase + d.token + '/'); } else { btn.textContent = '🔒 Private'; btn.style.color = '#94a3b8'; btn.style.borderColor = 'rgba(255,255,255,.1)'; btn.style.background = 'rgba(255,255,255,.04)'; api.setLastAction('Public link disabled'); } }); };
})();
