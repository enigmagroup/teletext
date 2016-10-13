t.run_xhr = true;

t.xhr_step = 10;

t.xhr_load = function() {
  var $xhr, xhr_url;
  $xhr = $('.xhr');
  xhr_url = $xhr.data('xhr-url');
  if (xhr_url) {
    if (xhr_url.indexOf('?') > -1) {
      xhr_url += '&step=' + t.xhr_step;
    } else {
      xhr_url += '?step=' + t.xhr_step;
    }
    if (t.run_xhr) {
      t.run_xhr = false;
      return $.get(xhr_url, function(data) {
        if (data.length > 1) {
          $xhr.append(data);
          t.xhr_step = t.xhr_step + 10;
          return t.run_xhr = true;
        } else {
          return t.run_xhr = false;
        }
      });
    }
  }
};
