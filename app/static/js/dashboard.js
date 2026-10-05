/* PoshanSathi — dashboard charts (Phase 11).
 *
 * Every dashboard template embeds its chart data as JSON in a
 * <script type="application/json" id="...-chart-data"> element and an empty
 * <canvas id="...Chart">.  This file turns each present pair into a Chart.js
 * chart.  All data comes from the database via the dashboard service.
 */

(function () {
  'use strict';

  var PALETTE = [
    '#2e7d32', '#1565c0', '#ef6c00', '#6a1b9a',
    '#00838f', '#c62828', '#f9a825', '#37474f'
  ];

  function readData(elementId) {
    var el = document.getElementById(elementId);
    if (!el) {
      return null;
    }
    try {
      return JSON.parse(el.textContent);
    } catch (error) {
      return null;
    }
  }

  function hasData(series, keys) {
    if (!series || !series.labels || series.labels.length === 0) {
      return false;
    }
    if (!keys) {
      return true;
    }
    return keys.some(function (key) {
      return Array.isArray(series[key]) && series[key].some(function (v) { return v !== null; });
    });
  }

  function render(canvasId, dataId, build) {
    var canvas = document.getElementById(canvasId);
    var data = readData(dataId);
    if (!canvas || !data || !window.Chart) {
      return;
    }
    var config = build(data);
    if (config) {
      new Chart(canvas, config);
    }
  }

  function lineDataset(label, values, colour, yAxisID) {
    return {
      label: label,
      data: values,
      borderColor: colour,
      backgroundColor: colour + '22',
      fill: true,
      tension: 0.3,
      spanGaps: true,
      yAxisID: yAxisID || 'y',
    };
  }

  function barDataset(label, values, colour, yAxisID) {
    return {
      label: label,
      data: values,
      backgroundColor: colour + 'cc',
      borderRadius: 4,
      yAxisID: yAxisID || 'y',
    };
  }

  function baseOptions(extraScales) {
    return {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: 'index', intersect: false },
      plugins: { legend: { position: 'bottom' } },
      scales: extraScales || { y: { beginAtZero: true, ticks: { precision: 0 } } },
    };
  }

  document.addEventListener('DOMContentLoaded', function () {
    if (!window.Chart) {
      return;
    }

    // Attendance trend (stacked daily present/absent bars).
    render('attendanceChart', 'attendance-chart-data', function (data) {
      if (!hasData(data, ['present', 'absent'])) {
        return null;
      }
      return {
        type: 'bar',
        data: {
          labels: data.labels,
          datasets: [
            barDataset('Present', data.present, '#2e7d32'),
            barDataset('Absent', data.absent, '#c62828'),
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { position: 'bottom' } },
          scales: {
            x: { stacked: true },
            y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } },
          },
        },
      };
    });

    // Doughnut helper for status breakdowns.
    function doughnut(canvasId, dataId, fallbackEmpty) {
      render(canvasId, dataId, function (data) {
        var entries = Object.keys(data)
          .filter(function (key) { return data[key] > 0; })
          .map(function (key, index) {
            return { label: key, value: data[key], colour: PALETTE[index % PALETTE.length] };
          });
        if (!entries.length && !fallbackEmpty) {
          return null;
        }
        return {
          type: 'doughnut',
          data: {
            labels: entries.length ? entries.map(function (e) { return e.label; }) : ['No data'],
            datasets: [{
              data: entries.length ? entries.map(function (e) { return e.value; }) : [1],
              backgroundColor: entries.length
                ? entries.map(function (e) { return e.colour; })
                : ['#e0e0e0'],
              borderWidth: 1,
            }],
          },
          options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { position: 'bottom' } },
          },
        };
      });
    }

    doughnut('vaccinationChart', 'vaccination-chart-data', false);
    doughnut('alertChart', 'alert-chart-data', false);

    // Nutrition distribution by item (bar).
    render('nutritionChart', 'nutrition-chart-data', function (data) {
      if (!data.labels || !data.labels.length) {
        return null;
      }
      return {
        type: 'bar',
        data: {
          labels: data.labels,
          datasets: [barDataset('Distributed', data.values, '#ef6c00')],
        },
        options: baseOptions({
          y: { beginAtZero: true, title: { display: true, text: 'Quantity' } },
          x: { ticks: { maxRotation: 45, minRotation: 0 } },
        }),
      };
    });

    // Centre comparison (grouped bars: children + mothers per centre).
    render('centreChart', 'centre-chart-data', function (data) {
      if (!data.labels || !data.labels.length) {
        return null;
      }
      return {
        type: 'bar',
        data: {
          labels: data.labels,
          datasets: [
            barDataset('Children', data.children, '#2e7d32'),
            barDataset('Mothers', data.mothers, '#6a1b9a'),
          ],
        },
        options: baseOptions({
          y: { beginAtZero: true, ticks: { precision: 0 } },
          x: { ticks: { maxRotation: 45, minRotation: 0 } },
        }),
      };
    });
  });
})();
