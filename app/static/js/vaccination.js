/* PoshanSathi — vaccination form helpers (Phase 5). */

document.addEventListener('DOMContentLoaded', function () {
  var status = document.getElementById('status');
  var administered = document.getElementById('administered_date');
  if (!status || !administered) {
    return;
  }

  function syncAdministeredDate() {
    var completed = status.value === 'COMPLETED';
    administered.required = completed;
    administered.disabled = false;
  }

  status.addEventListener('change', syncAdministeredDate);
  syncAdministeredDate();
});
