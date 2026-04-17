/* ═══════════════════════════════════════════════════════════════════
   NEXYZA PRESENTATION ENGINE
   — Pure overlay, no browser fullscreen API
   — Works on both result.html and gallery.html
   ═══════════════════════════════════════════════════════════════════ */


window.NXPresentDebug = true;
function _nxpLog(){
  try { console.log.apply(console, ['[NXPresent]'].concat([].slice.call(arguments))); } catch(e) {}
}
function _nxpWarn(){
  try { console.warn.apply(console, ['[NXPresent]'].concat([].slice.call(arguments))); } catch(e) {}
}
function _nxpFail(msg, meta){
  try {
    console.error('[NXPresent] ' + msg, meta || '');
    console.trace('[NXPresent] trace for: ' + msg);
  } catch(e) {}
  throw new Error('[NXPresent] ' + msg);
}

var _fsSlides      = [];
var _fsIndex       = 0;
var _fsChartInst   = null;
var _fsAutoTimer   = null;
var _fsAutoplaying = false;
var _fsAutoMs      = 5000;

// Saved card state for restore
var _fsSavedCard   = null;
var _fsSavedParent = null;
var _fsSavedNext   = null;   // next sibling before move
var _fsSavedStyle  = null;
var _fsSavedBodyStyle = null;

// ── Collect all visible chart cards into slide list ────────────────
function _fsBuildSlides(filter) {
  _nxpLog('buildSlides:start', {filter: filter});
  _fsSlides = [];
  var cards = document.querySelectorAll('.chart-card-wrapper[id^="cw-"]');
  cards.forEach(function(card) {
    if (card.style.display === 'none') return;
    var cid   = card.id.replace('cw-', '');
    var type  = card.getAttribute('data-type') || '';
    var title = card.querySelector('[title]');
    title = title ? title.getAttribute('title') : type;

    if (filter === 'kpis' && type !== 'kpi') return;
    if (filter === 'charts' && type === 'kpi') return;

    if (type === 'kpi') {
      // Extract value from the big gradient text element
      var valEl = card.querySelector('[id^="body-"] p');
      var lblEl = valEl ? valEl.nextElementSibling : null;
      _fsSlides.push({
        cid:   cid, title: title, type: 'kpi',
        value: valEl ? valEl.textContent.trim() : '—',
        label: lblEl ? lblEl.textContent.trim() : '',
      });
    } else {
      // Prefer live Chart.js instance
      var inst = window.DLCharts && window.DLCharts[cid];
      var data = null;
      if (inst && inst.data && inst.data.datasets && inst.data.datasets.length) {
        try {
          data = JSON.parse(JSON.stringify({
            labels:    inst.data.labels   || [],
            datasets:  inst.data.datasets || [],
            chart_type: inst.config.type  || type,
          }));
        } catch(e) {}
      }
      // Fallback: embedded JSON
      if (!data) {
        var jsonEl = document.getElementById('fs-data-' + cid);
        if (jsonEl) {
          try {
            var p = JSON.parse(jsonEl.textContent || '{}');
            if (p.datasets && p.datasets.length) data = p;
          } catch(e) {}
        }
      }
      if (data) {
        _fsSlides.push({
          cid: cid, title: title,
          type: type || data.chart_type || 'bar',
          data: data,
        });
      }
    }
  });
  _nxpLog('buildSlides:done', {filter: filter, slideCount: _fsSlides.length, slides: _fsSlides.map(function(s){ return {cid:s.cid,type:s.type,title:s.title}; })});
}

// ── Open overlay on one specific chart ────────────────────────────
window.openFullscreen = function(cid) {
  _nxpLog('openFullscreen:click', {cid: cid});
  _fsBuildSlides('all');
  if (!_fsSlides.length) { _nxpFail('No slides were built for openFullscreen()', {cid: cid}); }
  var idx = _fsSlides.findIndex(function(s){ return s.cid == cid; });
  _fsIndex = idx >= 0 ? idx : 0;
  _fsOpen();
};

// ── Present all / by mode ─────────────────────────────────────────
window.presentAll = function() { _fsPresentMode('all'); };
window.presentMode = function(mode) { _fsPresentMode(mode); };

function _fsPresentMode(filter) {
  _nxpLog('presentMode:click', {filter: filter});
  _fsBuildSlides(filter);
  if (!_fsSlides.length) { _nxpFail('No slides were built for presentMode()', {filter: filter}); }
  _fsIndex = 0;
  _fsOpen();
}

function _fsOpen() {
  var overlay = document.getElementById('nxp-overlay');
  _nxpLog('openOverlay', {hasOverlay: !!overlay});
  if (!overlay) _nxpFail('Presenter overlay #nxp-overlay was not found');
  _fsRenderDots();
  overlay.classList.add('open');
  overlay.style.display = 'flex';
  overlay.style.visibility = 'visible';
  overlay.style.opacity = '1';
  overlay.style.zIndex = '2147483647';
  overlay.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
  document.documentElement.style.overflow = 'hidden';
  try {
    var cs = window.getComputedStyle(overlay);
    _nxpLog('openOverlay:styles', {display: cs.display, visibility: cs.visibility, opacity: cs.opacity, zIndex: cs.zIndex});
  } catch(e) {}
  setTimeout(function(){ _fsShowSlide(_fsIndex, 0); }, 50);
}

// ── Render a slide ─────────────────────────────────────────────────
function _fsShowSlide(idx, dir) {
  var slide = _fsSlides[idx];
  _nxpLog('showSlide', {idx: idx, dir: dir, hasSlide: !!slide});
  if (!slide) _nxpFail('Slide index could not be resolved', {idx: idx, total: _fsSlides.length});
  _fsIndex = idx;

  // Update header
  var el = function(id){ return document.getElementById(id); };
  if (el('nxp-title'))   el('nxp-title').textContent   = slide.title;
  if (el('nxp-insight')) el('nxp-insight').textContent = '';
  if (el('nxp-counter')) el('nxp-counter').textContent = (idx+1) + ' / ' + _fsSlides.length;
  if (el('nxp-prev'))    el('nxp-prev').disabled = (idx === 0);
  if (el('nxp-next'))    el('nxp-next').disabled = (idx === _fsSlides.length - 1);

  // Dots
  document.querySelectorAll('.nxp-dot').forEach(function(d,i){
    d.classList.toggle('active', i === idx);
  });

  // Type buttons
  document.querySelectorAll('.nxp-type-btn').forEach(function(b){
    b.style.display = slide.type === 'kpi' ? 'none' : 'inline-flex';
    b.classList.toggle('active', b.dataset.type === (slide.type || 'bar'));
  });

  // Destroy previous chart
  if (_fsChartInst){ try{ _fsChartInst.destroy(); }catch(e){} _fsChartInst = null; }
  try { var prior = (window.Chart && Chart.getChart) ? Chart.getChart(document.getElementById('nxp-canvas')) : null; if (prior) prior.destroy(); } catch(e) {}
  _fsRestoreCard();

  var canvasWrap = el('nxp-canvas-wrap');
  var kpiSlide   = el('nxp-kpi-slide');

  // Slide-in animation
  if (canvasWrap && dir !== 0) {
    canvasWrap.classList.remove('fs-anim-fwd','fs-anim-rev');
    void canvasWrap.offsetWidth;
    canvasWrap.classList.add(dir > 0 ? 'fs-anim-fwd' : 'fs-anim-rev');
  }

  if (slide.type === 'kpi') {
    if (canvasWrap) canvasWrap.style.display = 'none';
    if (kpiSlide)   kpiSlide.style.display   = 'flex';
    var kv = el('nxp-kpi-value'), kl = el('nxp-kpi-label');
    if (kv) kv.textContent = slide.value;
    if (kl) kl.textContent = slide.label;
  } else {
    if (kpiSlide)   kpiSlide.style.display   = 'none';
    if (canvasWrap) canvasWrap.style.display = 'block';

    // Try mounting the live card first — it looks best
    if (!_fsMountCard(slide)) {
      // Fall back to rendering on the standalone canvas
      setTimeout(function(){ _fsRenderCanvas(slide); }, 60);
    }
  }
}

// ── Move the live card into the overlay ───────────────────────────
function _fsMountCard(slide) {
  var host    = document.getElementById('nxp-canvas-wrap');
  var area    = document.getElementById('nxp-chart-area');
  var card    = document.getElementById('cw-' + slide.cid);
  if (!host || !card || !card.parentNode) {
    _nxpWarn('mountCard skipped', {hasHost: !!host, hasCard: !!card, hasParent: !!(card && card.parentNode), cid: slide && slide.cid});
    return false;
  }

  // Save position
  _fsSavedCard      = card;
  _fsSavedParent    = card.parentNode;
  _fsSavedNext      = card.nextSibling;
  _fsSavedStyle     = card.getAttribute('style') || '';
  var body          = document.getElementById('body-' + slide.cid);
  _fsSavedBodyStyle = body ? (body.getAttribute('style') || '') : null;

  // Move card
  host.innerHTML = '';
  host.appendChild(card);
  card.classList.add('fs-live-card');
  card.style.cssText = [
    'width:min(1200px,100%)!important',
    'max-width:100%!important',
    'margin:0 auto',
    'height:100%',
    'grid-column:span 1!important',
    'display:flex',
    'flex-direction:column',
  ].join(';');

  if (body && area) {
    body.style.height = Math.max(360, area.clientHeight - 80) + 'px';
    body.style.flexShrink = '0';
  }

  // Resize the chart inside
  var inst = window.DLCharts && window.DLCharts[slide.cid];
  requestAnimationFrame(function(){
    requestAnimationFrame(function(){
      if (inst) { try{ inst.resize(); inst.update('none'); }catch(e){} }
    });
  });
  return true;
}

// ── Restore card to original position ─────────────────────────────
function _fsRestoreCard() {
  if (!_fsSavedCard) return;
  try {
    if (_fsSavedNext && _fsSavedNext.parentNode === _fsSavedParent) {
      _fsSavedParent.insertBefore(_fsSavedCard, _fsSavedNext);
    } else {
      _fsSavedParent.appendChild(_fsSavedCard);
    }
  } catch(e) {}

  _fsSavedCard.classList.remove('fs-live-card');
  _fsSavedCard.setAttribute('style', _fsSavedStyle);

  var body = document.getElementById('body-' + _fsSavedCard.id.replace('cw-',''));
  if (body && _fsSavedBodyStyle !== null) body.setAttribute('style', _fsSavedBodyStyle);

  var cid  = _fsSavedCard.id.replace('cw-','');
  var inst = window.DLCharts && window.DLCharts[cid];
  requestAnimationFrame(function(){
    requestAnimationFrame(function(){
      if (inst){ try{ inst.resize(); inst.update('none'); }catch(e){} }
    });
  });

  // Reset canvas wrap
  var host = document.getElementById('nxp-canvas-wrap');
  if (host) host.innerHTML = '<canvas id="nxp-canvas" style="display:none"></canvas>';

  _fsSavedCard = _fsSavedParent = _fsSavedNext = _fsSavedStyle = _fsSavedBodyStyle = null;
}

// ── Render standalone Chart.js on fs-canvas (fallback) ────────────
function _fsRenderCanvas(slide) {
  _nxpLog('renderCanvas:start', {cid: slide && slide.cid, type: slide && slide.type});
  if (_fsChartInst){ try{ _fsChartInst.destroy(); }catch(e){} _fsChartInst = null; }

  var wrap = document.getElementById('nxp-canvas-wrap');
  var area = document.getElementById('nxp-chart-area');
  if (!wrap || !area) _nxpFail('Presenter canvas host missing', {hasWrap: !!wrap, hasArea: !!area});

  var r = area.getBoundingClientRect();
  var w = Math.max(320, r.width  - 120);
  var h = Math.max(320, r.height - 40);

  wrap.style.width    = w + 'px';
  wrap.style.height   = h + 'px';
  wrap.style.maxWidth = wrap.style.maxHeight = '100%';
  wrap.innerHTML = '<canvas id="nxp-canvas"></canvas>';

  var canvas = document.getElementById('nxp-canvas');
  if (!canvas) _nxpFail('Presenter canvas #nxp-canvas was not created');
  canvas.style.cssText = 'display:block;width:100%;height:100%;';
  canvas.width = w; canvas.height = h;

  var d = slide.data || {labels:[],datasets:[]};
  var type  = slide.type || 'bar';
  var isH   = type === 'horizontal_bar';
  var jsType = {area:'line',histogram:'bar',horizontal_bar:'bar',variance_bar:'bar',waterfall:'bar',bullet:'bar',progress_ring:'doughnut'}[type] || type;
  _nxpLog('renderCanvas:typeMapping', {requestedType: type, jsType: jsType});
  var isPie = jsType === 'pie' || jsType === 'doughnut';
  var tick  = {color:'#64748b', font:{size:13}};
  var grid  = {color:'rgba(255,255,255,.06)', drawBorder:false};
  var scales = {};
  if (!isPie) {
    scales = isH
      ? {x:{grid:grid,ticks:tick}, y:{grid:{color:'rgba(255,255,255,.04)',drawBorder:false},ticks:tick}}
      : {x:{grid:{color:'rgba(255,255,255,.04)',drawBorder:false},ticks:Object.assign({},tick,{maxRotation:30})}, y:{grid:grid,ticks:tick}};
  }
  try {
    _fsChartInst = new Chart(canvas.getContext('2d'), {
      type: isH ? 'bar' : jsType,
      data: {
        labels:   (d.labels   || []).slice(),
        datasets: (d.datasets || []).map(function(ds){
          var c = Object.assign({},ds);
          if (Array.isArray(ds.data)) c.data = ds.data.slice();
          return c;
        }),
      },
      options: {
        indexAxis: isH ? 'y' : 'x',
        responsive: true, maintainAspectRatio: false,
        animation: {duration:250},
        interaction: {mode:'nearest',intersect:false},
        plugins: {
          legend: {
            display: (d.datasets||[]).length > 1 || isPie,
            position: isPie ? 'right' : 'top',
            labels: {color:'#94a3b8',font:{size:13},boxWidth:12,padding:16},
          },
          tooltip: {enabled:true},
        },
        scales: scales,
      },
    });
    requestAnimationFrame(function(){
      requestAnimationFrame(function(){
        if (_fsChartInst && canvas.isConnected){
          try{ _fsChartInst.resize(w,h); _fsChartInst.update('none'); }catch(e){}
        }
      });
    });
  } catch(e) {
    console.error('[NXPresent] Chart render failed', e, {slide: slide});
    wrap.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#475569;font-size:14px;">Chart failed to render</div>';
    throw e;
  }
}

// ── Navigation ─────────────────────────────────────────────────────
window.fsNavigate = function(dir) {
  var n = _fsIndex + dir;
  if (n < 0 || n >= _fsSlides.length) return;
  _fsShowSlide(n, dir);
};
window.fsGoTo = function(idx) {
  if (idx < 0 || idx >= _fsSlides.length) return;
  _fsShowSlide(idx, idx > _fsIndex ? 1 : -1);
};

// ── Dots ───────────────────────────────────────────────────────────
function _fsRenderDots() {
  var track = document.getElementById('nxp-dots');
  if (!track) return;
  track.innerHTML = '';
  var max = Math.min(_fsSlides.length, 40);
  for (var i = 0; i < max; i++) {
    (function(i){
      var b = document.createElement('button');
      b.className = 'nxp-dot' + (i === _fsIndex ? ' active' : '');
      b.title = (_fsSlides[i]||{}).title || '';
      b.addEventListener('click', function(){ fsGoTo(i); });
      track.appendChild(b);
    })(i);
  }
  if (_fsSlides.length > 40) {
    track.insertAdjacentHTML('beforeend',
      '<span style="color:#374151;font-size:10px;margin-left:6px;">+'+(_fsSlides.length-40)+'</span>');
  }
}

// ── Autoplay ───────────────────────────────────────────────────────
window.fsToggleAutoplay = function() {
  _fsAutoplaying = !_fsAutoplaying;
  var btn = document.getElementById('nxp-autoplay-btn');
  if (_fsAutoplaying) {
    if (btn){ btn.textContent='⏸ Auto'; btn.classList.add('active'); }
    _fsAutoTimer = setInterval(function(){
      if (_fsIndex < _fsSlides.length-1) fsNavigate(1);
      else _fsShowSlide(0,1);
    }, _fsAutoMs);
  } else {
    if (btn){ btn.textContent='▶ Auto'; btn.classList.remove('active'); }
    clearInterval(_fsAutoTimer); _fsAutoTimer = null;
  }
};

// ── Close ──────────────────────────────────────────────────────────
window.closeFullscreen = function() {
  _nxpLog('closeFullscreen');
  var overlay = document.getElementById('nxp-overlay');
  if (overlay) {
    overlay.classList.remove('open');
    overlay.style.display = 'none';
    overlay.style.visibility = 'hidden';
    overlay.style.opacity = '0';
    overlay.setAttribute('aria-hidden', 'true');
  }
  document.body.style.overflow = '';
  document.documentElement.style.overflow = '';
  if (_fsChartInst){ try{ _fsChartInst.destroy(); }catch(e){} _fsChartInst=null; }
  _fsRestoreCard();
  if (_fsAutoTimer){ clearInterval(_fsAutoTimer); _fsAutoTimer=null; _fsAutoplaying=false; }
  var btn = document.getElementById('nxp-autoplay-btn');
  if (btn){ btn.textContent='▶ Auto'; btn.classList.remove('active'); }
  document.querySelectorAll('.nxp-type-btn').forEach(function(b){ b.style.display=''; });
};

// ── Change type on active slide ────────────────────────────────────
window.fsChangeType = function(type) {
  document.querySelectorAll('.nxp-type-btn').forEach(function(b){
    b.classList.toggle('active', b.dataset.type===type);
  });
  var slide = _fsSlides[_fsIndex];
  if (slide && slide.type !== 'kpi') {
    slide.type = type;
    if (window.changeType) changeType(slide.cid, type);
  }
};

// ── Download ───────────────────────────────────────────────────────
window.fsDownload = function(fmt) {
  var slide  = _fsSlides[_fsIndex];
  var fname  = ((slide&&slide.title)||'chart').replace(/[^a-z0-9]/gi,'_').toLowerCase()+'.'+fmt;
  var link   = document.createElement('a');
  link.download = fname;
  var src = slide ? document.getElementById('cc-'+slide.cid) : null;
  var cv  = document.getElementById('nxp-canvas');
  if (src)                         link.href = src.toDataURL('image/png');
  else if (cv && _fsChartInst)     link.href = cv.toDataURL('image/png');
  else return;
  link.click();
};

// ── Keyboard ───────────────────────────────────────────────────────
document.addEventListener('keydown', function(e) {
  var overlay = document.getElementById('nxp-overlay');
  if (!overlay || !overlay.classList.contains('open')) return;
  switch(e.key) {
    case 'Escape':                   closeFullscreen();    break;
    case 'ArrowLeft':
    case 'ArrowUp':   e.preventDefault(); fsNavigate(-1); break;
    case 'ArrowRight':
    case 'ArrowDown': e.preventDefault(); fsNavigate(1);  break;
    case ' ':         e.preventDefault(); fsToggleAutoplay(); break;
    case 'Home':      e.preventDefault(); fsGoTo(0);       break;
    case 'End':       e.preventDefault(); fsGoTo(_fsSlides.length-1); break;
  }
});

window._fsBuildSlides = _fsBuildSlides;
window._fsSlides = _fsSlides;

window.nxpDebugPresent = function(mode){
  _nxpLog('nxpDebugPresent invoked', {mode: mode || 'all'});
  return (mode && mode !== 'all') ? window.presentMode(mode) : window.presentAll();
};
console.log('[NXPresent] presenter script loaded');
