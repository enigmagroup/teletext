t.char_counter = function() {
  var $charcounter, $telegram, $transmit;
  $telegram = $('#telegram');
  $transmit = $('#transmit');
  $charcounter = $('.charcounter');
  return $telegram.on('keyup', function() {
    var available_chars, remaining_chars, str_len;
    available_chars = 256;
    str_len = $telegram.val().length;
    remaining_chars = available_chars - str_len;
    $charcounter.text(remaining_chars);
    if (remaining_chars < 0) {
      $charcounter.addClass('warning');
      return $transmit.attr('disabled', 'disabled');
    } else {
      $charcounter.removeClass('warning');
      return $transmit.attr('disabled', false);
    }
  });
};
