/* =========================================
   ATLAS AI -- Shared Chart.js styling helpers
   Used by every page that renders an equity curve, so charts look
   and behave identically everywhere (smoother lines, real gradient
   fills, consistent tooltips/grid, currency-formatted axes) instead
   of each page re-implementing its own chart config.
   ========================================= */

function atlasFormatCurrency(value) {
    return "$" + Number(value).toLocaleString(undefined, {
        minimumFractionDigits: 2, maximumFractionDigits: 2,
    });
}

function atlasGradientFill(chart, color) {
    const area = chart.chartArea;
    if (!area) return color + "22";
    const gradient = chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
    gradient.addColorStop(0, color + "4a");
    gradient.addColorStop(1, color + "02");
    return gradient;
}

function atlasTrendColor(points) {
    if (!points || points.length < 2) return "#4fd1c5";
    return points[points.length - 1].equity >= points[0].equity ? "#4ade80" : "#f87171";
}

/**
 * Renders (or re-renders) an equity curve line chart with the shared
 * Atlas look: smooth line, gradient fill, hover tooltip with exact
 * currency value, sparse currency-formatted y-axis, sparse date
 * x-axis, and a colour that reflects whether the visible window is
 * net up or down.
 */
function renderAtlasEquityChart(canvasId, points, options) {
    options = options || {};
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;

    const color = options.color || atlasTrendColor(points);

    return new Chart(ctx, {
        type: "line",
        data: {
            labels: points.map(p => p.label),
            datasets: [{
                data: points.map(p => p.equity),
                borderColor: color,
                backgroundColor: (context) => atlasGradientFill(context.chart, color),
                fill: true,
                pointRadius: 0,
                pointHitRadius: 12,
                pointHoverRadius: 4,
                pointHoverBackgroundColor: color,
                pointHoverBorderColor: "#0b0f14",
                pointHoverBorderWidth: 2,
                borderWidth: 2,
                tension: 0.35,
                cubicInterpolationMode: "monotone",
            }],
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            interaction: { mode: "index", intersect: false },
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#0e141bf2",
                    borderColor: "#202b38",
                    borderWidth: 1,
                    titleColor: "#8a99a8",
                    titleFont: { size: 11 },
                    bodyColor: "#eef2f6",
                    bodyFont: { size: 13, weight: "bold" },
                    padding: 10,
                    displayColors: false,
                    callbacks: {
                        label: (item) => atlasFormatCurrency(item.parsed.y),
                    },
                },
            },
            scales: {
                x: {
                    display: !options.hideAxes,
                    ticks: { color: "#5f6c7a", font: { size: 10 }, maxTicksLimit: 6, maxRotation: 0, autoSkip: true },
                    grid: { display: false },
                    border: { color: "#202b38" },
                },
                y: {
                    display: !options.hideAxes,
                    ticks: {
                        color: "#8a99a8", font: { size: 10 }, maxTicksLimit: 5,
                        callback: (v) => "$" + Number(v).toLocaleString(),
                    },
                    grid: { color: "#151d27" },
                    border: { display: false },
                },
            },
        },
    });
}

function renderAtlasSparkline(canvasId, values, color) {
    const ctx = document.getElementById(canvasId);
    if (!ctx) return null;
    return new Chart(ctx, {
        type: "line",
        data: {
            labels: values.map((_, i) => i),
            datasets: [{
                data: values,
                borderColor: color,
                borderWidth: 1.5,
                pointRadius: 0,
                tension: 0.35,
                fill: false,
            }],
        },
        options: {
            responsive: false,
            plugins: { legend: { display: false }, tooltip: { enabled: false } },
            scales: { x: { display: false }, y: { display: false } },
        },
    });
}
