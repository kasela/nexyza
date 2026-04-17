(function(){
  function fallbackToast(msg){
    var t = document.getElementById('nexyza-chart-toast');
    if(!t){
      t = document.createElement('div');
      t.id = 'nexyza-chart-toast';
      t.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:9999;background:#0f172a;border:1px solid rgba(124,58,237,.35);color:#e2e8f0;border-radius:12px;padding:10px 14px;font-size:12px;box-shadow:0 12px 32px rgba(0,0,0,.45);opacity:0;transform:translateY(8px);transition:all .18s ease;';
      document.body.appendChild(t);
    }
    t.textContent = '✓ ' + msg;
    t.style.opacity = '1';
    t.style.transform = 'translateY(0)';
    clearTimeout(t._hideTimer);
    t._hideTimer = setTimeout(function(){
      t.style.opacity = '0';
      t.style.transform = 'translateY(8px)';
    }, 2200);
  }

  function showToast(msg){
    if(typeof window.showToast === 'function' && window.showToast !== api.showToast){
      try { return window.showToast(msg); } catch(e) {}
    }
    return fallbackToast(msg);
  }

  function getChartInstance(cid){
    return window.DLCharts && window.DLCharts[cid] ? window.DLCharts[cid] : null;
  }

  function getRawChartData(cid){
    return window.DLChartMeta && window.DLChartMeta[cid] ? window.DLChartMeta[cid].raw : null;
  }

  function toggleMenu(id){
    var el = document.getElementById(id);
    if(!el) return;
    var open = el.classList.contains('open');
    document.querySelectorAll('.tb-menu.open').forEach(function(m){ m.classList.remove('open'); });
    if(!open) el.classList.add('open');
  }

  function closeMenu(menuId){
    if(!menuId) return;
    var el = document.getElementById(menuId);
    if(el) el.classList.remove('open');
  }

  function triggerDownload(url, filename){
    var a = document.createElement('a');
    a.href = url;
    a.download = filename || '';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    setTimeout(function(){ a.remove(); }, 0);
  }

  function downloadChart(cid, fmt){
    var inst = getChartInstance(cid);
    if(!inst){ showToast('Chart not loaded'); return; }
    var url = inst.toBase64Image();
    triggerDownload(url, 'chart-' + cid + '.' + (fmt || 'png'));
    showToast('Downloaded as ' + String(fmt || 'png').toUpperCase());
    closeMenu('dl-menu-' + cid);
  }

  function quickDownload(cid){
    return downloadChart(cid, 'png');
  }

  function copyChartData(cid){
    var raw = getRawChartData(cid);
    var rows = [];
    if(raw && raw.labels && raw.datasets){
      rows.push(raw.labels.join('\t'));
      (raw.datasets || []).forEach(function(ds){ rows.push((ds.data || []).join('\t')); });
    } else {
      var inst = getChartInstance(cid);
      if(!inst){ showToast('Chart not loaded'); return; }
      rows.push((inst.data.labels || []).join('\t'));
      (inst.data.datasets || []).forEach(function(ds){ rows.push((ds.data || []).join('\t')); });
    }
    if(!navigator.clipboard || !navigator.clipboard.writeText){
      showToast('Clipboard unavailable');
      return;
    }
    navigator.clipboard.writeText(rows.join('\n')).then(function(){
      showToast('Data copied to clipboard');
      closeMenu('dl-menu-' + cid);
    }).catch(function(){
      showToast('Copy failed');
    });
  }

  function bindGlobalMenuClose(){
    if(document.body && document.body.dataset.chartActionMenusBound === '1') return;
    if(document.body) document.body.dataset.chartActionMenusBound = '1';
    document.addEventListener('click', function(e){
      if(!e.target.closest('.tb-dropdown')){
        document.querySelectorAll('.tb-menu.open').forEach(function(m){ m.classList.remove('open'); });
      }
    });
  }

  var api = {
    toggleMenu: toggleMenu,
    closeMenu: closeMenu,
    showToast: fallbackToast,
    downloadChart: downloadChart,
    quickDownload: quickDownload,
    copyChartData: copyChartData,
    getChartInstance: getChartInstance,
    getRawChartData: getRawChartData
  };

  window.NexyzaChartActions = api;
  window.toggleMenu = toggleMenu;
  if(typeof window.showToast !== 'function'){
    window.showToast = fallbackToast;
  }
  window.downloadChart = downloadChart;
  window.quickDownload = quickDownload;
  window.copyChartData = copyChartData;

  if(document.readyState === 'loading'){
    document.addEventListener('DOMContentLoaded', bindGlobalMenuClose);
  } else {
    bindGlobalMenuClose();
  }
})();
