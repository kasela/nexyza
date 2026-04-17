
(function(){
  const cfgEl = document.getElementById('report-export-config');
  if(!cfgEl) return;
  let cfg = {};
  try { cfg = JSON.parse(cfgEl.textContent || '{}'); } catch(e) { return; }

  const listEl = document.getElementById('report-export-history-list');
  const queueBtn = document.getElementById('report-export-queue-btn');
  const refreshBtn = document.getElementById('report-export-history-refresh');

  function renderJobs(jobs){
    if(!listEl) return;
    if(!jobs || !jobs.length){
      listEl.innerHTML = '<div style="font-size:12px;color:#64748b;">No report exports yet.</div>';
      return;
    }
    listEl.innerHTML = jobs.map(function(job){
      var tone = job.status === 'done' ? '#86efac' : (job.status === 'error' ? '#fca5a5' : '#fde68a');
      var bg   = job.status === 'done' ? 'rgba(16,185,129,.08)' : (job.status === 'error' ? 'rgba(239,68,68,.08)' : 'rgba(245,158,11,.08)');
      var actions = '';
      if(job.download_url){
        actions += '<a href="'+job.download_url+'" style="padding:6px 10px;border-radius:8px;border:1px solid rgba(16,185,129,.2);background:rgba(16,185,129,.08);color:#86efac;font-size:11px;text-decoration:none;">Download</a>';
      }
      actions += '<button type="button" data-retry="'+job.id+'" style="padding:6px 10px;border-radius:8px;border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);color:#cbd5e1;font-size:11px;cursor:pointer;">Retry</button>';
      return '<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;flex-wrap:wrap;padding:10px 12px;border-radius:12px;background:'+bg+';border:1px solid rgba(255,255,255,.06);">'
      + '<div style="min-width:220px;">'
      +   '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">'
      +     '<span style="font-size:11px;padding:4px 10px;border-radius:999px;background:rgba(255,255,255,.05);color:'+tone+';border:1px solid rgba(255,255,255,.08);text-transform:uppercase;letter-spacing:.04em;">'+job.status+'</span>'
      +     '<span style="font-size:11px;color:#e2e8f0;font-weight:600;">'+(job.fmt || 'pdf').toUpperCase()+'</span>'
      +     '<span style="font-size:11px;color:#64748b;">'+(job.created_at || '')+'</span>'
      +   '</div>'
      +   '<div style="margin-top:5px;font-size:11px;color:#94a3b8;">'+(job.message || job.error || 'Ready')+'</div>'
      + '</div>'
      + '<div style="display:flex;align-items:center;gap:8px;">'+actions+'</div>'
      + '</div>';
    }).join('');
  }

  function loadHistory(){
    if(!cfg.historyUrl || !listEl) return;
    fetch(cfg.historyUrl, {headers:{'X-Requested-With':'XMLHttpRequest'}})
      .then(function(r){ return r.json(); })
      .then(function(data){ renderJobs(data.jobs || []); })
      .catch(function(){ listEl.innerHTML = '<div style="font-size:12px;color:#fca5a5;">Could not load export history.</div>'; });
  }

  function queueExport(fmt){
    if(!cfg.queueUrl) return;
    if(queueBtn){ queueBtn.disabled = true; queueBtn.textContent = 'Queueing…'; }
    var url = cfg.queueUrl.replace('/pdf/queue/', '/' + (fmt || 'pdf') + '/queue/');
    fetch(url, {method:'POST', headers:{'X-CSRFToken':cfg.csrfToken,'X-Requested-With':'XMLHttpRequest'}})
      .then(function(r){ return r.json().then(function(data){ return {ok:r.ok, data:data}; }); })
      .then(function(res){ if(!res.ok || !res.data.ok){ throw new Error((res.data && (res.data.error || (res.data.field_errors && Object.values(res.data.field_errors)[0]))) || 'Could not queue export.'); } loadHistory(); })
      .catch(function(err){ if(listEl){ listEl.innerHTML = '<div style="font-size:12px;color:#fca5a5;">'+ (err && err.message ? err.message : 'Could not queue export.') +'</div>'; } })
      .finally(function(){ if(queueBtn){ queueBtn.disabled = false; queueBtn.textContent = '⏳ Queue PDF'; } });
  }

  function retryExport(jobId){
    fetch((cfg.retryBaseUrl || '') + jobId + '/', {method:'POST', headers:{'X-CSRFToken':cfg.csrfToken,'X-Requested-With':'XMLHttpRequest'}})
      .then(function(r){ return r.json().then(function(data){ return {ok:r.ok, data:data}; }); })
      .then(function(res){ if(!res.ok || !res.data.ok){ throw new Error((res.data && res.data.error) || 'Could not retry export.'); } loadHistory(); })
      .catch(function(err){ if(listEl){ listEl.innerHTML = '<div style="font-size:12px;color:#fca5a5;">'+ (err && err.message ? err.message : 'Could not retry export.') +'</div>'; } });
  }

  if(queueBtn){
    queueBtn.addEventListener('click', function(){ queueExport(this.dataset.fmt || 'pdf'); });
  }
  if(refreshBtn){ refreshBtn.addEventListener('click', loadHistory); }
  if(listEl){
    listEl.addEventListener('click', function(e){
      var btn = e.target.closest('[data-retry]');
      if(btn) retryExport(btn.getAttribute('data-retry'));
    });
  }
  document.addEventListener('report-export-history:refresh', loadHistory);
  loadHistory();
})();
