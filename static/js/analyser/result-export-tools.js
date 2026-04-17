(function(){
  function readConfig(){
    var node = document.getElementById('result-export-config');
    if (!node) return null;
    try { return JSON.parse(node.textContent || node.innerText || '{}'); } catch (e) { return null; }
  }

  function init(){
    var cfg = readConfig();
    if (!cfg || !cfg.uploadId) return;

    var uploadId = cfg.uploadId;
    var csrf = cfg.csrf || '';
    var pinUrl = cfg.pinUrl || '';
    var exportPdfUrl = cfg.exportPdfUrl || ('/export/' + uploadId + '/pdf/queue/');
    var exportPptxUrl = cfg.exportPptxUrl || ('/export/' + uploadId + '/pptx/queue/');
    var exportStatusBase = cfg.exportStatusBase || '/export/status/';
    var selectedThemeUploadId = null;

    window.togglePin = function togglePin(){
      if (!pinUrl) return;
      fetch(pinUrl, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      }).then(function(r){ return r.json(); }).then(function(d){
        var btn = document.getElementById('pin-btn');
        if (btn) {
          btn.textContent = d.pinned ? '📌' : '📍';
          btn.title = d.pinned ? 'Unpin from dashboard' : 'Pin to dashboard';
        }
      }).catch(function(err){
        console.error('Pin toggle failed', err);
      });
    };

    function showToast(html) {
      var t = document.getElementById('export-toast');
      if (!t) {
        t = document.createElement('div');
        t.id = 'export-toast';
        t.style.cssText = [
          'position:fixed;bottom:24px;right:24px;z-index:9999',
          'background:#1e1b2e;border:1px solid rgba(124,58,237,.4)',
          'border-radius:14px;padding:14px 20px;color:#e2e8f0;font-size:13px',
          'box-shadow:0 8px 32px rgba(0,0,0,.6);min-width:280px;max-width:360px'
        ].join(';');
        document.body.appendChild(t);
      }
      t.innerHTML = html;
      return t;
    }

    function showDownloadToast(toast, label, url) {
      toast.innerHTML =
        '<div style="display:flex;align-items:flex-start;gap:12px;">' +
          '<span style="color:#34d399;font-size:20px;line-height:1;">&#10003;</span>' +
          '<div>' +
            '<p style="margin:0 0 6px;font-weight:600;">' + label + ' ready!</p>' +
            '<a href="' + url + '" download ' +
              'style="display:inline-block;background:linear-gradient(135deg,#7c3aed,#3b82f6);' +
              'color:#fff;padding:7px 16px;border-radius:8px;font-size:12px;' +
              'font-weight:600;text-decoration:none;">' +
              '&#8595; Download ' + label +
            '</a>' +
            '<button data-export-dismiss="1" ' +
              'style="display:block;margin-top:8px;background:none;border:none;' +
              'color:#475569;font-size:11px;cursor:pointer;padding:0;">Dismiss</button>' +
          '</div>' +
        '</div>';
      var a = document.createElement('a');
      a.href = url;
      a.download = '';
      a.style.display = 'none';
      document.body.appendChild(a);
      a.click();
      setTimeout(function(){ a.remove(); }, 1000);
    }

    function pollExport(jobId, label, toast) {
      var tries = 0;
      var interval = setInterval(function() {
        tries++;
        if (tries > 60) {
          clearInterval(interval);
          toast.innerHTML = '<p style="margin:0;color:#f87171;">Export timed out. Please try again.</p>';
          setTimeout(function(){ toast.remove(); }, 5000);
          return;
        }
        fetch(exportStatusBase + jobId + '/')
          .then(function(r){ return r.json(); })
          .then(function(d){
            if (window.dispatchEvent) {
              window.dispatchEvent(new CustomEvent('nexyza:export-job-updated', { detail: d }));
            }
            if (d.status === 'done') {
              clearInterval(interval);
              showDownloadToast(toast, label, d.url);
            } else if (d.status === 'error') {
              clearInterval(interval);
              toast.innerHTML = '<p style="margin:0;color:#f87171;">&#9888; ' + (d.error || 'Export failed') + '</p>';
              setTimeout(function(){ toast.remove(); }, 6000);
            }
          })
          .catch(function(err){
            clearInterval(interval);
            toast.innerHTML = '<p style="margin:0;color:#f87171;">&#9888; Export polling failed.</p>';
            setTimeout(function(){ toast.remove(); }, 5000);
            console.error('Export polling error:', err);
          });
      }, 1500);
    }

    function doExport(fmt, uploadIdArg, theme) {
      var label = fmt === 'pdf' ? 'PDF' : 'PowerPoint';
      var spinner = '<div style="width:16px;height:16px;border:2px solid #7c3aed;border-top-color:transparent;border-radius:50%;animation:spin 1s linear infinite;flex-shrink:0;"></div>';
      var toast = showToast(
        '<div style="display:flex;align-items:center;gap:10px;">' + spinner +
        '<div><p style="margin:0;font-weight:600;">Generating ' + label + '…</p>' +
        '<p style="margin:3px 0 0;color:#64748b;font-size:11px;">Please wait, do not close this tab</p></div></div>'
      );

      var url = fmt === 'pdf' ? exportPdfUrl : exportPptxUrl;
      if (fmt === 'pptx' && theme) {
        url += '?theme=' + encodeURIComponent(theme);
      }

      fetch(url, {
        method: 'POST',
        headers: { 'X-CSRFToken': csrf }
      })
      .then(function(r) {
        if (!r.ok) throw new Error('Server error ' + r.status);
        return r.json();
      })
      .then(function(d) {
        if (window.dispatchEvent) {
          window.dispatchEvent(new CustomEvent('nexyza:export-job-updated', { detail: d }));
        }
        if (d.status === 'done' && d.url) {
          showDownloadToast(toast, label, d.url);
        } else if (d.status === 'error') {
          toast.innerHTML = '<p style="margin:0;color:#f87171;">&#9888; ' + (d.error || 'Export failed') + '</p>';
          setTimeout(function() { toast.remove(); }, 6000);
        } else if (d.job_id) {
          pollExport(d.job_id, label, toast);
        } else {
          throw new Error('Unexpected response');
        }
      })
      .catch(function(err) {
        toast.innerHTML = '<p style="margin:0;color:#f87171;">&#9888; Export failed. Please try again.</p>';
        setTimeout(function(){ toast.remove(); }, 5000);
        console.error('Export error:', err);
      });
    }

    function ensureThemePicker(){
      var m = document.getElementById('pptx-theme-modal');
      if (m) return m;
      m = document.createElement('div');
      m.id = 'pptx-theme-modal';
      m.style.cssText = 'position:fixed;inset:0;z-index:9999;background:rgba(0,0,0,.75);backdrop-filter:blur(6px);display:flex;align-items:center;justify-content:center;padding:20px;';
      m.innerHTML = [
        '<div style="background:#1e1b2e;border:1px solid rgba(124,58,237,.3);border-radius:20px;padding:28px 32px;max-width:520px;width:100%;">',
        '<p style="color:#fff;font-size:1.1rem;font-weight:700;margin:0 0 6px;">Choose PowerPoint Theme</p>',
        '<p style="color:#64748b;font-size:13px;margin:0 0 20px;">Select a visual style for your presentation.</p>',
        '<div id="pptx-theme-grid" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:20px;"></div>',
        '<div style="display:flex;gap:10px;">',
        '<button class="btn-primary" style="flex:1;justify-content:center;" id="pptx-start-btn" disabled>Generate PowerPoint →</button>',
        '<button id="pptx-cancel-btn" class="btn-secondary" style="padding:10px 18px;">Cancel</button>',
        '</div></div>'
      ].join('');
      document.body.appendChild(m);

      var themes = [
        {id:'dark', label:'Dark', bg:'#0F0C1E', text:'#e2e0f0', accent:'#7c3aed', desc:'Midnight dark background'},
        {id:'light', label:'Light', bg:'#F8FAFC', text:'#1e293b', accent:'#7c3aed', desc:'Clean white background'},
        {id:'corporate', label:'Corporate', bg:'#1E3A5F', text:'#F0F4F8', accent:'#3b82f6', desc:'Deep navy professional'},
        {id:'minimal', label:'Minimal', bg:'#FFFFFF', text:'#0F172A', accent:'#7c3aed', desc:'Pure white, no distractions'}
      ];
      var grid = m.querySelector('#pptx-theme-grid');
      grid.innerHTML = themes.map(function(t){
        return '<button type="button" class="pptx-theme-option" data-theme="' + t.id + '" ' +
          'style="background:' + t.bg + ';border:2px solid rgba(124,58,237,.2);border-radius:12px;padding:14px;cursor:pointer;text-align:left;transition:.15s;">' +
          '<p style="color:' + t.text + ';font-weight:700;font-size:13px;margin:0 0 3px;">' + t.label + '</p>' +
          '<p style="color:' + t.text + ';opacity:.6;font-size:11px;margin:0;">' + t.desc + '</p>' +
          '<div style="margin-top:8px;height:4px;border-radius:999px;background:' + t.accent + ';"></div>' +
          '</button>';
      }).join('');

      grid.addEventListener('click', function(e){
        var btn = e.target.closest('[data-theme]');
        if (!btn) return;
        grid.querySelectorAll('[data-theme]').forEach(function(node){
          node.style.borderColor = 'rgba(124,58,237,.2)';
          node.dataset.selected = '';
        });
        btn.style.borderColor = 'rgba(124,58,237,.7)';
        btn.dataset.selected = '1';
        var startBtn = document.getElementById('pptx-start-btn');
        if (startBtn) {
          startBtn.disabled = false;
          startBtn.dataset.theme = btn.dataset.theme;
        }
      });
      m.querySelector('#pptx-cancel-btn').addEventListener('click', function(){ m.remove(); });
      m.querySelector('#pptx-start-btn').addEventListener('click', function(){
        var theme = this.dataset.theme || 'dark';
        m.remove();
        doExport('pptx', selectedThemeUploadId || uploadId, theme);
      });
      return m;
    }

    window.showThemePicker = function showThemePicker(uploadIdArg) {
      selectedThemeUploadId = uploadIdArg || uploadId;
      var modal = ensureThemePicker();
      modal.style.display = 'flex';
      var startBtn = document.getElementById('pptx-start-btn');
      if (startBtn) {
        startBtn.disabled = true;
        startBtn.dataset.theme = '';
      }
      modal.querySelectorAll('[data-theme]').forEach(function(node){
        node.style.borderColor = 'rgba(124,58,237,.2)';
        node.dataset.selected = '';
      });
    };

    window.requestExport = function requestExport(fmt, uploadIdArg) {
      if (fmt === 'pptx') {
        window.showThemePicker(uploadIdArg || uploadId);
        return;
      }
      if (typeof window.toggleMenu === 'function') {
        try { window.toggleMenu('export-menu'); } catch (e) {}
      }
      doExport(fmt, uploadIdArg || uploadId, 'dark');
    };

    document.addEventListener('click', function(e){
      if (e.target && e.target.matches('[data-export-dismiss="1"]')) {
        var toast = document.getElementById('export-toast');
        if (toast) toast.remove();
      }
    });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
