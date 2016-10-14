
t.mentions_userlist = false

t.mentions = ->
    $telegram = $('#telegram')

    $telegram.on 'focus', ->
        if not t.mentions_userlist
            $.get "/api/v1/get_subscription.json?type=subscriptions", (data) ->
                t.mentions_userlist = []
                for u in data.user_list
                    t.mentions_userlist.push u.name
                t.mentions_atwho()
        else
            t.mentions_atwho()

t.mentions_atwho = ->
    $telegram = $('#telegram')

    $telegram.atwho
        at: "@"
        data: t.mentions_userlist
