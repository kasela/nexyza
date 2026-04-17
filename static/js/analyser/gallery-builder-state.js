(function(){
  function ensureNs(){
    window.NexyzaGallery = window.NexyzaGallery || {};
    return window.NexyzaGallery;
  }
  var ns = ensureNs();

  ns.safeText = ns.safeText || function(v){ return (v == null ? '' : String(v)); };
  ns.readConfig = ns.readConfig || function(){
    var node = document.getElementById('gallery-page-config');
    if (!node) return null;
    try { return JSON.parse(node.textContent || node.innerText || '{}'); } catch (e) { return null; }
  };

  ns.makeBuilderState = function makeBuilderState(ctx){
    function readValue(id){
      var el = document.getElementById(id);
      return el ? (el.value || '') : '';
    }
    function setValue(id, value){
      var el = document.getElementById(id);
      if (el) el.value = value || '';
    }
    function persistBuilderState(){
      var state = {
        type: ctx.BP.type,
        color: ctx.BP.color,
        x: readValue('bp-x'),
        y: readValue('bp-y'),
        agg: readValue('bp-agg'),
        group: readValue('bp-group'),
        title: readValue('bp-title'),
        size: readValue('bp-size'),
        xlabel: readValue('bp-xlabel'),
        ylabel: readValue('bp-ylabel'),
        insight: readValue('bp-insight'),
        extras: Array.from(document.querySelectorAll('input[name="bp-extra"]:checked')).map(function(c){ return c.value; })
      };
      try { localStorage.setItem(ctx.BUILDER_KEY, JSON.stringify(state)); } catch (e) {}
    }
    function restoreBuilderState(){
      try {
        var raw = localStorage.getItem(ctx.BUILDER_KEY);
        if (!raw) return;
        var state = JSON.parse(raw);
        setValue('bp-x', state.x);
        setValue('bp-y', state.y);
        setValue('bp-agg', state.agg || 'mean');
        setValue('bp-group', state.group);
        setValue('bp-title', state.title);
        setValue('bp-size', state.size || 'md');
        setValue('bp-xlabel', state.xlabel);
        setValue('bp-ylabel', state.ylabel);
        setValue('bp-insight', state.insight);
        ctx.BP.type = state.type || ctx.BP.type;
        ctx.BP.color = state.color || ctx.BP.color;
        document.querySelectorAll('.ctype-btn').forEach(function(b){ b.classList.toggle('active', b.dataset.type === ctx.BP.type); });
        document.querySelectorAll('.color-swatch').forEach(function(s){ s.classList.toggle('active', s.dataset.color === ctx.BP.color); });
        var extras = state.extras || [];
        document.querySelectorAll('input[name="bp-extra"]').forEach(function(c){ c.checked = extras.indexOf(c.value) !== -1; });
      } catch (e) {}
    }
    function bindBuilderPersistence(){
      ['bp-x','bp-y','bp-agg','bp-group','bp-title','bp-size','bp-xlabel','bp-ylabel','bp-insight'].forEach(function(id){
        var el = document.getElementById(id);
        if (!el || el.dataset.persistBound === '1') return;
        el.dataset.persistBound = '1';
        el.addEventListener('change', persistBuilderState);
        el.addEventListener('input', persistBuilderState);
      });
      document.querySelectorAll('input[name="bp-extra"]').forEach(function(c){
        if (c.dataset.persistBound === '1') return;
        c.dataset.persistBound = '1';
        c.addEventListener('change', persistBuilderState);
      });
    }
    return {
      readValue: readValue,
      setValue: setValue,
      persistBuilderState: persistBuilderState,
      restoreBuilderState: restoreBuilderState,
      bindBuilderPersistence: bindBuilderPersistence,
    };
  };
})();
