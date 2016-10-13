
t = t || {}

$(document).ready ->
    t.char_counter()
    t.xhr()
    t.timeline_poller()
    t.bind_subscribe_buttons()
    t.bind_retransmit()
    t.bind_delete()
