(function () {
    var ctx = document.getElementById('dashboard-trend-chart');
    if (!ctx) return;
    var data = window.__DASHBOARD_TREND__ || [];
    if (typeof Chart === 'undefined') return;
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: data.map(function (d) { return d.date; }),
            datasets: [{
                label: 'Выручка, ₽',
                data: data.map(function (d) { return d.revenue; }),
                borderColor: 'rgb(75, 192, 192)',
                fill: false
            }]
        },
        options: {
            responsive: true,
            scales: { y: { beginAtZero: true } }
        }
    });
})();
