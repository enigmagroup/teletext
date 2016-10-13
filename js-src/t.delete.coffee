
t.bind_delete = ->
    $modal_window = $('#modal-window')
    $modal_submit = $('#submit')
    submit_text = 'Delete'

    $('.timeline, .telegram').on 'click', '.delete',  (ev) ->
        $modal_window.find('h3').text 'Delete this telegram?'
        $modal_submit.text submit_text
        $modal_submit.attr 'data-action', 'delete'
        telegram = $(ev.target).parents('li').html()
        $('.modal-body', $modal_window).html telegram
        $modal_window.modal()

    $modal_submit.on 'click', ->
        if $modal_submit.data('action') == 'delete'
            ipv6 = $('.modal-body .ipv6').text()
            created_at = $('.modal-body .created_at').data 'created_at'

            $modal_submit.text('Working...').attr 'disabled', 'disabled'
            $.post '/xhr/delete',
                'ipv6': ipv6,
                'created_at': created_at,
            , (data) ->
                if data.result == 'success'
                    $modal_window.modal 'hide'
                else
                    console.error 'failed.'
                    $modal_window.modal 'hide'
                $modal_submit.text(original_text).attr 'disabled', false
