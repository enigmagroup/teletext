t.bind_delete = function() {
  var $modal_submit, $modal_window, submit_text;
  $modal_window = $('#modal-window');
  $modal_submit = $('#submit');
  submit_text = 'Delete';
  $('.timeline, .telegram').on('click', '.delete', function(ev) {
    var telegram;
    $modal_window.find('h3').text('Delete this telegram?');
    $modal_submit.text(submit_text);
    $modal_submit.attr('data-action', 'delete');
    telegram = $(ev.target).parents('li').html();
    $('.modal-body', $modal_window).html(telegram);
    return $modal_window.modal();
  });
  return $modal_submit.on('click', function() {
    var created_at, ipv6;
    if ($modal_submit.data('action') === 'delete') {
      ipv6 = $('.modal-body .ipv6').text();
      created_at = $('.modal-body .created_at').data('created_at');
      $modal_submit.text('Working...').attr('disabled', 'disabled');
      return $.post('/xhr/delete', {
        'ipv6': ipv6,
        'created_at': created_at
      }, function(data) {
        if (data.result === 'success') {
          $modal_window.modal('hide');
        } else {
          console.error('failed.');
          $modal_window.modal('hide');
        }
        return $modal_submit.text(original_text).attr('disabled', false);
      });
    }
  });
};
