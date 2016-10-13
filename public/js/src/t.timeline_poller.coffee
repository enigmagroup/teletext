
t.run_timeline_xhr = true

t.timeline_xhr = ->
    $timeline = $('.timeline')
    xhr_url = $timeline.data('xhr-url')
    t.timeline_newest = $('li:first .created_at', $timeline).data('created_at')

    if xhr_url

        if xhr_url.indexOf('?') > -1
            xhr_url += '&since=' + t.timeline_newest
        else
            xhr_url += '?since=' + t.timeline_newest

        if window.location.href.indexOf('/fc') > -1
            # don't run on profile pages
            t.run_timeline_xhr = false

        if t.run_timeline_xhr
            t.run_timeline_xhr = false
            $.get xhr_url, (data) ->
                if data.length > 1
                    $timeline.prepend data
                t.run_timeline_xhr = true

t.timeline_poller = ->
    setInterval ->
        t.timeline_xhr()
    , 2000
