
t.bind_subscribe_buttons = ->
    $subscribe_button = $('.subscribe')

    $subscribe_button.each (i, button) ->
        $button = $(button)
        ipv6 = $button.val()

        if $button.attr('name') == 'subscribe'

            original_text = $button.text()
            $button.text('Checking...').attr 'disabled', 'disabled'

            $.get '/xhr/check_status',
                'ipv6': ipv6
            , (data) ->
                if data.result == 'pong'
                    $button.text(original_text).attr 'disabled', false
                else
                    $button.text('Disabled')
                    $dropdown = $button.parents('.buttonblock').find '.dropdown-toggle'
                    $dropdown.attr 'disabled', 'disabled'

    # bind events
    $subscribe_button.on 'click', (ev) ->
        $btn = $(ev.target)
        ipv6 = $btn.val()
        what = $btn.attr('name')

        original_text = $btn.text()
        $btn.text('Working...').attr('disabled', 'disabled')

        $.post '/xhr/subscribe',
            'what': what,
            'ipv6': ipv6,
        , (data) ->
            if data.result == 'success'
                if what == 'subscribe'
                    $btn.removeClass('btn-default').addClass 'btn-success'
                    $btn.attr 'name', 'unsubscribe'
                    $btn.text 'Subscribed'
                else
                    $btn.removeClass('btn-success').addClass 'btn-default'
                    $btn.attr 'name', 'subscribe'
                    $btn.text 'Subscribe'
            else
                $btn.text original_text
            $btn.attr 'disabled', false
        return false
