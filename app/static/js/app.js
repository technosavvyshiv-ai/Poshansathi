/* PoshanSathi — global client-side behaviour (Phase 0 foundation) */

document.addEventListener('DOMContentLoaded', function () {
  // Auto-dismiss flash messages after a short delay.
  document.querySelectorAll('.alert-dismissible').forEach(function (el) {
    setTimeout(function () {
      if (window.bootstrap) {
        var alert = bootstrap.Alert.getOrCreateInstance(el);
        alert.close();
      }
    }, 6000);
  });
});
