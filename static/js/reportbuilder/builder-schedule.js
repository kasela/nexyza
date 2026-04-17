(function(){
  var api = window.NexyzaReportBuilder = window.NexyzaReportBuilder || {};
  if (!api.cfg) return;
  function updateSchedulePill(active, frequency){
    var pill = document.getElementById('report-schedule-pill');
    if (!pill) return;
    if (active) {
      pill.textContent = 'Scheduled · ' + (frequency || 'Weekly').replace(/^./, function(m){ return m.toUpperCase(); });
      pill.style.background = 'rgba(16,185,129,.12)';
      pill.style.borderColor = 'rgba(16,185,129,.2)';
      pill.style.color = '#86efac';
    } else {
      pill.textContent = 'Not scheduled';
      pill.style.background = 'rgba(255,255,255,.04)';
      pill.style.borderColor = 'rgba(255,255,255,.08)';
      pill.style.color = '#94a3b8';
    }
  }
  function showScheduleFeedback(text, ok){
    var s = document.getElementById('sched-status');
    if (!s) return;
    s.style.display = 'block';
    s.style.color = ok ? '#34d399' : '#f87171';
    s.textContent = text;
  }
  function renderFieldErrors(map){
    var parts = [];
    Object.keys(map || {}).forEach(function(key){ if (map[key]) parts.push(map[key]); });
    return parts.join(' ');
  }
  function preloadSchedule(){
    var active = api.cfg.activeSchedule || {};
    var freq = document.getElementById('sched-freq');
    var email = document.getElementById('sched-email');
    if (freq && active.frequency) freq.value = active.frequency;
    if (email && active.email) email.value = active.email;
    updateSchedulePill(!!active.frequency, active.frequency);
  }
  window.saveSchedule = function(){
    var btn = document.getElementById('sched-save-btn');
    if (!btn) return;
    btn.textContent = 'Saving…'; btn.disabled = true;
    var frequency = (document.getElementById('sched-freq') || {}).value || 'weekly';
    var email = (document.getElementById('sched-email') || {}).value || '';
    var fd = new FormData();
    fd.append('csrfmiddlewaretoken', api.CSRF);
    fd.append('frequency', frequency);
    fd.append('email', email);
    fetch(api.cfg.scheduleUrl, {method:'POST', body:fd})
      .then(function(r){ return r.json(); })
      .then(function(d){
        btn.textContent = 'Save Schedule'; btn.disabled = false;
        if (d.ok) {
          showScheduleFeedback('✓ Scheduled — next delivery ' + (d.next_send_at || ('in 1 ' + frequency.replace('ly',''))), true);
          api.cfg.activeSchedule = {frequency: frequency, email: email};
          updateSchedulePill(true, frequency);
          api.setLastAction('Schedule saved');
          setTimeout(function(){ var m = document.getElementById('schedule-modal'); if (m) m.style.display='none'; var s = document.getElementById('sched-status'); if (s) s.style.display='none'; }, 2500);
        } else {
          showScheduleFeedback((d.error || 'Failed to save schedule') + (d.field_errors ? ' ' + renderFieldErrors(d.field_errors) : ''), false);
        }
      })
      .catch(function(){
        btn.textContent = 'Save Schedule'; btn.disabled = false;
        showScheduleFeedback('Network error while saving schedule.', false);
      });
  };
  document.addEventListener('DOMContentLoaded', preloadSchedule);
})();
