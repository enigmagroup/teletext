
t.run_xhr = true
t.xhr_step = 10

t.xhr_load = ->
    $xhr = $('.xhr');
    xhr_url = $xhr.data('xhr-url');

    if xhr_url
        if xhr_url.indexOf('?') > -1
            xhr_url += '&step=' + t.xhr_step
        else
            xhr_url += '?step=' + t.xhr_step

        if t.run_xhr
            t.run_xhr = false
            $.get xhr_url, (data) ->
                if data.length > 1
                    $xhr.append data
                    t.xhr_step = t.xhr_step + 10
                    t.run_xhr = true
                else
                    t.run_xhr = false
