/* PoshanSathi — child growth trend chart (Phase 4). */

document.addEventListener('DOMContentLoaded', function () {
  var dataEl = document.getElementById('growth-chart-data');
  var canvas = document.getElementById('growthChart');
  if (!dataEl || !canvas || !window.Chart) {
    return;
  }

  var series;
  try {
    series = JSON.parse(dataEl.textContent);
  } catch (error) {
    return;
  }
  if (!series.labels || series.labels.length === 0) {
    return;
  }

  new Chart(canvas, {
    type: 'line',
    data: {
      labels: series.labels,
      datasets: [
        {
          label: 'Weight (kg)',
          data: series.weight,
          borderColor: '#2e7d32',
          backgroundColor: 'rgba(46, 125, 50, 0.12)',
          tension: 0.25,
          spanGaps: true,
          yAxisID: 'y',
        },
        {
          label: 'Height (cm)',
          data: series.height,
          borderColor: '#1565c0',
          backgroundColor: 'rgba(21, 101, 192, 0.10)',
          tension: 0.25,
          spanGaps: true,
          yAxisID: 'y1',
        },
        {
          label: 'MUAC (cm)',
          data: series.muac,
          borderColor: '#ef6c00',
          backgroundColor: 'rgba(239, 108, 0, 0.10)',
          tension: 0.25,
          spanGaps: true,
          yAxisID: 'y1',
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: { position: 'bottom' },
        tooltip: { mode: 'index', intersect: false },
      },
      scales: {
        y: {
          position: 'left',
          title: { display: true, text: 'Weight (kg)' },
        },
        y1: {
          position: 'right',
          title: { display: true, text: 'Height / MUAC (cm)' },
          grid: { drawOnChartArea: false },
        },
      },
    },
  });
});
