(function(){
  function parseConfig(){
    var el = document.getElementById('chart-mutation-config');
    if(!el) return null;
    try { return JSON.parse(el.textContent); } catch(e) { return null; }
  }

  var config = parseConfig() || {};

  function getCsrf(){
    if(config.csrf) return config.csrf;
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function buildUpdateUrl(cid){
    if(config.updateUrlTemplate){
      return String(config.updateUrlTemplate).replace('__CID__', encodeURIComponent(cid));
    }
    if(config.uploadId){
      return '/workspace/' + encodeURIComponent(config.uploadId) + '/charts/' + encodeURIComponent(cid) + '/update/';
    }
    return null;
  }

  function updateChart(cid, data){
    var url = buildUpdateUrl(cid);
    if(!url){
      if(window.showToast) window.showToast('Chart update route unavailable');
      return Promise.reject(new Error('Missing chart mutation URL'));
    }
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'X-CSRFToken': getCsrf()
      },
      body: new URLSearchParams(data)
    }).then(function(response){
      if(!response.ok) throw new Error('Chart update failed');
      var contentType = response.headers.get('content-type') || '';
      return contentType.indexOf('application/json') >= 0 ? response.json() : {};
    });
  }

  function closeMenu(id){
    if(window.NexyzaChartActions && typeof window.NexyzaChartActions.closeMenu === 'function'){
      window.NexyzaChartActions.closeMenu(id);
    } else {
      var el = document.getElementById(id);
      if(el) el.classList.remove('open');
    }
  }

  function destroyChart(cid){
    if(window.DLCharts && window.DLCharts[cid]){
      try { window.DLCharts[cid].destroy(); } catch(e) {}
      delete window.DLCharts[cid];
    }
  }

  function resizeChart(cid){
    if(window.DLCharts && window.DLCharts[cid] && typeof window.DLCharts[cid].resize === 'function'){
      try { window.DLCharts[cid].resize(); } catch(e) {}
    }
  }

  function setBodyLoading(cid, isLoading){
    var body = document.getElementById('body-' + cid);
    if(body) body.style.opacity = isLoading ? '.4' : '1';
  }

  function applySizePreview(cid, newSize){
    var wrapper = document.getElementById('cw-' + cid);
    var spanMap = {sm:'span 1', md:'span 1', lg:'span 2', full:'span 2'};
    var heightMap = {sm:'180px', md:'210px', lg:'260px', full:'260px'};
    if(wrapper) wrapper.style.gridColumn = spanMap[newSize] || 'span 1';
    var body = document.getElementById('body-' + cid);
    if(body) body.style.height = heightMap[newSize] || '210px';
  }

  function hardReload(){
    window.location.reload();
  }

  function changeType(cid, newType){
    setBodyLoading(cid, true);
    destroyChart(cid);
    updateChart(cid, {chart_type:newType}).then(function(){
      setBodyLoading(cid, false);
      hardReload();
    }).catch(function(){
      setBodyLoading(cid, false);
      if(window.showToast) window.showToast('Could not change chart type');
    });
    closeMenu('type-menu-' + cid);
  }

  function changeColor(cid, newColor){
    updateChart(cid, {color:newColor}).then(function(){
      hardReload();
    }).catch(function(){
      if(window.showToast) window.showToast('Could not change chart colour');
    });
    closeMenu('color-menu-' + cid);
  }

  function changeSize(cid, newSize){
    applySizePreview(cid, newSize);
    updateChart(cid, {size:newSize}).then(function(){
      resizeChart(cid);
    }).catch(function(){
      if(window.showToast) window.showToast('Could not change chart size');
    });
    closeMenu('size-menu-' + cid);
  }

  window.NexyzaChartMutations = {
    updateChart: updateChart,
    changeType: changeType,
    changeColor: changeColor,
    changeSize: changeSize,
    getCsrf: getCsrf,
    buildUpdateUrl: buildUpdateUrl
  };
  window.changeType = changeType;
  window.changeColor = changeColor;
  window.changeSize = changeSize;
})();
