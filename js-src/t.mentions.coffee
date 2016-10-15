
t.mentions_userlist = false

t.mentions = ->
    $telegram = $('#telegram')

    $telegram.on 'focus', ->
        if not t.mentions_userlist
            $.get "/api/v1/get_subscription.json?type=subscriptions", (data) ->
                t.mentions_userlist = data.user_list

                $telegram.atwho
                    at: "@"
                    data: t.mentions_userlist
                    displayTpl: "<li>${name} <small>${ipv6}</small>"

                $telegram.on 'keyup', ->
                    t.mentions_checkhidden()

t.mentions_checkhidden = (value) ->
    console.info 'ch'
    if not $('input[name=mentions]').length
        $('#telegram').after '<input type="text" name="mentions" />'

    $('input[name=mentions]').val value
