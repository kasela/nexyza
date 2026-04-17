(function(){
  function readConfig(){
    var node = document.getElementById('result-export-config');
    if (!node) return null;
    try { return JSON.parse(node.textContent || node.innerText || '{}'); } catch (e) { return null; }
  }

  function fmtLabel(fmt){ return fmt === 'pptx' ? 'PowerPoint' : (fmt || '').toUpperCase(); }

  function init(){
    var cfg = readConfig();
    var list = document.getElementById('export-history-list');
    var empty = document.getElementById('export-history-empty');
    if (!cfg || !list || !cfg.exportHistoryUrl) return;

    var csrf = cfg.csrf || '';
    var statusBase = cfg.exportStatusBase || '/export/status/';
    var retryBase = cfg.exportRetryBase || '/export/retry/';
    var activePolls = Object.create(null);

    function badge(status){
      var map = {
        pending: 'background:rgba(59,130,246,.14);border:1px solid rgba(59,130,246,.35);color:#93c5fd;',
        done: 'background:rgba(16,185,129,.14);border:1px solid rgba(16,185,129,.3);color:#6ee7b7;',
        error: 'background:rgba(244,63,94,.14);border:1px solid rgba(244,63,94,.3);color:#fda4af;'
      };
      var label = status === 'done' ? 'Ready' : (status === 'error' ? 'Failed' : 'Queued');
      return '<span style="display:inline-flex;align-items:center;padding:4px 8px;border-radius:999px;font-size:11px;font-weight:700;' + (map[status] || map.pending) + '">' + label + '</span>';
    }

    function card(job){
      var updated = job.updated_at ? new Date(job.updated_at).toLocaleString() : '';
      var actions = '';
      if (job.status === 'done' && job.url) {
        actions += '<a href="' + job.url + '" class="btn-primary" style="font-size:11px;padding:6px 12px;text-decoration:none;">Download</a>';
      }
      if (job.status === 'error' || job.status === 'done') {
        actions += '<button type="button" class="btn-secondary export-retry-btn" data-job-id="' + job.job_id + '" style="font-size:11px;padding:6px 12px;">Retry</button>';
      }
      return '<div data-export-job-card="' + job.job_id + '" style="display:flex;align-items:flex-start;justify-content:space-between;gap:14px;flex-wrap:wrap;padding:12px 14px;border-radius:14px;background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);">' +
        '<div style="min-width:240px;flex:1;">' +
          '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:6px;">' +
            '<span style="color:#fff;font-weight:700;font-size:13px;">' + fmtLabel(job.fmt) + '</span>' + badge(job.status) +
            '<span style="color:#64748b;font-size:11px;">' + (job.theme || 'dark') + ' theme</span>' +
          '</div>' +
          '<p style="margin:0;color:#94a3b8;font-size:12px;">' + (updated || 'just now') + '</p>' +
          (job.error ? '<p style="margin:6px 0 0;color:#fda4af;font-size:12px;">' + job.error + '</p>' : '') +
        '</div>' +
        '<div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;">' + actions + '</div>' +
      '</div>';
    }

    function startPolling(jobId){
      if (!jobId || activePolls[jobId]) return;
      activePolls[jobId] = setInterval(function(){
        fetch(statusBase + jobId + '/')
          .then(function(r){ return r.json(); })
          .then(function(job){
            var node = list.querySelector('[data-export-job-card="' + jobId + '"]');
            if (node) node.outerHTML = card(job);
            if (job.status === 'done' || job.status === 'error') {
              clearInterval(activePolls[jobId]);
              delete activePolls[jobId];
            }
          })
          .catch(function(){
            clearInterval(activePolls[jobId]);
            delete activePolls[jobId];
          });
      }, 2000);
    }

    function render(jobs){
      list.innerHTML = (jobs || []).map(card).join('');
      empty.style.display = jobs && jobs.length ? 'none' : 'block';
      (jobs || []).forEach(function(job){ if (job.status === 'pending') startPolling(job.job_id); });
    }

    function refresh(){
      fetch(cfg.exportHistoryUrl)
        .then(function(r){ return r.json(); })
        .then(function(payload){ render(payload.jobs || []); })
        .catch(function(){ empty.style.display = 'block'; });
    }

    function retry(jobId){
      fetch(retryBase + jobId + '/', { method:'POST', headers:{ 'X-CSRFToken': csrf } })
        .then(function(r){ return r.json(); })
        .then(function(job){
          refresh();
          if (window.dispatchEvent) {
            window.dispatchEvent(new CustomEvent('nexyza:export-job-updated', { detail: job }));
          }
        });
    }

    list.addEventListener('click', function(e){
      var btn = e.target.closest('.export-retry-btn');
      if (!btn) return;
      retry(btn.dataset.jobId);
    });

    window.refreshExportHistory = refresh;
    window.addEventListener('nexyza:export-job-updated', refresh);
    refresh();
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
