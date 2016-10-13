
t.char_counter = ->
    $telegram = $('#telegram')
    $transmit = $('#transmit')
    $charcounter = $('.charcounter')
    $telegram.on 'keyup', ->
        available_chars = 256
        str_len = $telegram.val().length
        remaining_chars = (available_chars - str_len)
        $charcounter.text remaining_chars

        if remaining_chars < 0
            $charcounter.addClass 'warning'
            $transmit.attr 'disabled', 'disabled'
        else
            $charcounter.removeClass 'warning'
            $transmit.attr 'disabled', false
