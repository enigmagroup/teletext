t.bind_subscribe_buttons = function() {
  var $subscribe_button;
  $subscribe_button = $('.subscribe');
  $subscribe_button.each(function(i, button) {
    var $button, ipv6, original_text;
    $button = $(button);
    ipv6 = $button.val();
    if ($button.attr('name') === 'subscribe') {
      original_text = $button.text();
      $button.text('Checking...').attr('disabled', 'disabled');
      return $.get('/xhr/check_status', {
        'ipv6': ipv6
      }, function(data) {
        var $dropdown;
        if (data.result === 'pong') {
          return $button.text(original_text).attr('disabled', false);
        } else {
          $button.text('Disabled');
          $dropdown = $button.parents('.buttonblock').find('.dropdown-toggle');
          return $dropdown.attr('disabled', 'disabled');
        }
      });
    }
  });
  return $subscribe_button.on('click', function(ev) {
    var $btn, ipv6, original_text, what;
    $btn = $(ev.target);
    ipv6 = $btn.val();
    what = $btn.attr('name');
    original_text = $btn.text();
    $btn.text('Working...').attr('disabled', 'disabled');
    $.post('/xhr/subscribe', {
      'what': what,
      'ipv6': ipv6
    }, function(data) {
      if (data.result === 'success') {
        if (what === 'subscribe') {
          $btn.removeClass('btn-default').addClass('btn-success');
          $btn.attr('name', 'unsubscribe');
          $btn.text('Subscribed');
        } else {
          $btn.removeClass('btn-success').addClass('btn-default');
          $btn.attr('name', 'subscribe');
          $btn.text('Subscribe');
        }
      } else {
        $btn.text(original_text);
      }
      return $btn.attr('disabled', false);
    });
    return false;
  });
};
