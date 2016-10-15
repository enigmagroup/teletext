
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

t.mentions_checkhidden = ->
    $telegram = $('#telegram')
    $mentions = $('input[name=mentions]')
    mentions = []

    if not $mentions.length
        $telegram.after '<input type="text" class="input-xxlarge" name="mentions" />'

    for u in t.mentions_userlist
        if $telegram.val().indexOf('@' + u.name) > -1
            o = {}
            o[u.name] = u.ipv6
            mentions.push o

    $mentions.val JSON.stringify(mentions)
