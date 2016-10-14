
t.mentions_userlist = false

t.mentions = ->
    $telegram = $('#telegram')

    $telegram.on 'focus', ->
        if not t.mentions_userlist
            t.mentions_userlist = ['ois', 'two', 'three']

        t.mentions_atwho()

t.mentions_atwho = ->
    $telegram = $('#telegram')

    $telegram.atwho
        at: "@"
        # data: t.mentions_userlist
        data: do ->
            return t.mentions_userlist
