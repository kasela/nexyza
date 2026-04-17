(function(){
  function readConfig(){
    var node=document.getElementById('result-collab-config');
    if(!node) return null;
    try { return JSON.parse(node.textContent || '{}'); } catch(e) { return null; }
  }

  var config=readConfig();
  if(!config || !config.uploadId) return;

  var uploadId=config.uploadId;
  var commentsUrl=config.commentsUrl || ('/collab/' + uploadId + '/comments/');
  var presenceUrl=config.presenceUrl || ('/collab/' + uploadId + '/presence/');
  var wsUrl=(window.location.protocol==='https:'?'wss':'ws')+'://'+window.location.host+'/ws/analysis/'+uploadId+'/';
  var ws=null;
  var pingTimer=null;

  function updatePresence(users){
    var safeUsers=Array.isArray(users) ? users : [];
    var bar=document.getElementById('presence-avatars');
    var empty=document.getElementById('presence-empty');
    if(!bar) return;
    bar.innerHTML=safeUsers.map(function(u){
      var email=(u && u.user_email) || '';
      var initials=(u && u.initials) || '?';
      return '<div style="width:24px;height:24px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;color:#fff;background:linear-gradient(135deg,#7c3aed,#3b82f6);" title="'+email+'">'+initials+'</div>';
    }).join('');
    if(empty) empty.style.display=safeUsers.length ? 'none' : 'block';
  }

  function addComment(data){
    var list=document.getElementById('comment-list');
    if(!list) return;
    var empty=list.querySelector('p');
    if(empty) empty.remove();
    var author=(data && data.author) || 'User';
    var initials=(data && data.initials) || '?';
    var text=(data && data.text) || '';
    var el=document.createElement('div');
    el.style.cssText='background:rgba(255,255,255,0.04);border:1px solid var(--border);border-radius:8px;padding:8px 10px;font-size:12px;';
    el.innerHTML='<div style="display:flex;align-items:center;gap:6px;margin-bottom:4px;"><div style="width:18px;height:18px;border-radius:50%;background:linear-gradient(135deg,#7c3aed,#3b82f6);display:flex;align-items:center;justify-content:center;color:#fff;font-size:9px;font-weight:700;">'+initials+'</div><span style="color:#475569;font-size:11px;">'+author+'</span></div><p style="color:#94a3b8;margin:0;">'+text+'</p>';
    list.appendChild(el);
    list.scrollTop=list.scrollHeight;
  }

  function fetchPresence(){
    fetch(presenceUrl)
      .then(function(r){ return r.json(); })
      .then(function(d){ updatePresence((d && d.viewers) || []); })
      .catch(function(){});
  }

  function connect(){
    try{
      ws=new WebSocket(wsUrl);
      ws.onopen=function(){
        if(pingTimer) clearInterval(pingTimer);
        pingTimer=setInterval(function(){
          if(ws && ws.readyState===1) ws.send(JSON.stringify({type:'ping'}));
        },30000);
      };
      ws.onmessage=function(e){
        var data={};
        try{ data=JSON.parse(e.data || '{}'); }catch(err){ data={}; }
        if(data.type==='presence_list') updatePresence(data.users);
        else if(data.type==='presence_update') fetchPresence();
        else if(data.type==='new_comment') addComment(data);
      };
      ws.onclose=function(){
        if(pingTimer) clearInterval(pingTimer);
        setTimeout(connect,3000);
      };
    }catch(e){}
  }

  window.sendComment=function sendComment(){
    var inp=document.getElementById('comment-input');
    if(!inp || !inp.value.trim() || !ws || ws.readyState!==1) return;
    ws.send(JSON.stringify({type:'comment',text:inp.value.trim()}));
    inp.value='';
  };

  var commentInput=document.getElementById('comment-input');
  if(commentInput){
    commentInput.addEventListener('keydown',function(e){
      if(e.key==='Enter') window.sendComment();
    });
  }

  connect();
  fetch(commentsUrl)
    .then(function(r){ return r.json(); })
    .then(function(d){ ((d && d.comments) || []).forEach(addComment); })
    .catch(function(){});
})();
