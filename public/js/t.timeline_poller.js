t.run_timeline_xhr = true;

t.timeline_xhr = function() {
  var $timeline, xhr_url;
  $timeline = $('.timeline');
  xhr_url = $timeline.data('xhr-url');
  t.timeline_newest = $('li:first .created_at', $timeline).data('created_at');
  if (xhr_url) {
    if (xhr_url.indexOf('?') > -1) {
      xhr_url += '&since=' + t.timeline_newest;
    } else {
      xhr_url += '?since=' + t.timeline_newest;
    }
    if (window.location.href.indexOf('/fc') > -1) {
      t.run_timeline_xhr = false;
    }
    if (t.run_timeline_xhr) {
      t.run_timeline_xhr = false;
      return $.get(xhr_url, function(data) {
        if (data.length > 1) {
          $timeline.prepend(data);
        }
        return t.run_timeline_xhr = true;
      });
    }
  }
};

t.timeline_poller = function() {
  return setInterval(function() {
    return t.timeline_xhr();
  }, 2000);
};
