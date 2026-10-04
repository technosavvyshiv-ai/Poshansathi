/* PoshanSathi — beneficiary/centre client-side behaviour (Phase 3). */

document.addEventListener('DOMContentLoaded', function () {
  // Ask for confirmation before destructive form submissions.
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (event) {
      var message = form.getAttribute('data-confirm') || 'Are you sure?';
      if (!window.confirm(message)) {
        event.preventDefault();
      }
    });
  });
});
