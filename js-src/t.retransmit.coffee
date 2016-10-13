
t.bind_retransmit = ->
    $modal_window = $('#modal-window')
    $modal_submit = $('#submit')
    submit_text = 'Retransmit'

    $('.timeline, .telegram').on 'click', '.retransmit',  (ev) ->
        $modal_window.find('h3').text 'Retransmit this to your subscribers?'
        $modal_submit.text submit_text
        $modal_submit.attr 'data-action', 'retransmit'
        telegram = $(ev.target).parents('li').html()
        $('.modal-body', $modal_window).html telegram
        $modal_window.modal()

    $modal_submit.on 'click', ->
        if $modal_submit.data('action') == 'retransmit'
            ipv6 = $('.modal-body .ipv6').text()
            created_at = $('.modal-body .created_at').data 'created_at'

            $modal_submit.text('Working...').attr 'disabled', 'disabled'
            $.post '/xhr/retransmit',
                'ipv6': ipv6,
                'created_at': created_at,
            , (data) ->
                if data.result == 'success'
                    $modal_window.modal 'hide'
                else
                    console.error 'failed.'
                    $modal_window.modal 'hide'
                $modal_submit.text(submit_text).attr 'disabled', false
