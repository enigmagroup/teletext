var t;

t = t || {};

$(document).ready(function() {
  t.char_counter();
  t.xhr();
  t.timeline_poller();
  t.bind_subscribe_buttons();
  t.bind_retransmit();
  return t.bind_delete();
});
