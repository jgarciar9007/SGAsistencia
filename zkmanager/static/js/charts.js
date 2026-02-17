// ZKManager Charts - Chart.js Integration

// Initialize all charts on page load
document.addEventListener('DOMContentLoaded', function () {
    initializeCharts();
});

// Chart.js default configuration
Chart.defaults.font.family = "'Segoe UI', Tahoma, Geneva, Verdana, sans-serif";
Chart.defaults.color = '#2C3E50';

// Color palette
const colors = {
    primary: '#18A052',
    secondary: '#2C3E50',
    success: '#27AE60',
    warning: '#F39C12',
    danger: '#E74C3C',
    info: '#3498DB',
    light: '#ECF0F1',
    dark: '#34495E'
};

// Initialize all charts
function initializeCharts() {
    // Monthly attendance trend chart
    const monthlyTrendCanvas = document.getElementById('monthlyTrendChart');
    if (monthlyTrendCanvas) {
        createMonthlyTrendChart(monthlyTrendCanvas);
    }

    // Department comparison chart
    const deptComparisonCanvas = document.getElementById('deptComparisonChart');
    if (deptComparisonCanvas) {
        createDepartmentComparisonChart(deptComparisonCanvas);
    }

    // Late arrivals pie chart
    const lateArrivalsCanvas = document.getElementById('lateArrivalsChart');
    if (lateArrivalsCanvas) {
        createLateArrivalsChart(lateArrivalsCanvas);
    }

    // Weekly attendance heatmap
    const weeklyHeatmapCanvas = document.getElementById('weeklyHeatmapChart');
    if (weeklyHeatmapCanvas) {
        createWeeklyHeatmapChart(weeklyHeatmapCanvas);
    }
}

// Monthly Attendance Trend Chart
function createMonthlyTrendChart(canvas) {
    const ctx = canvas.getContext('2d');

    // Get data from data attributes or use defaults
    const labels = JSON.parse(canvas.dataset.labels || '[]');
    const data = JSON.parse(canvas.dataset.values || '[]');

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Asistencias',
                data: data,
                borderColor: colors.primary,
                backgroundColor: colors.primary + '20',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 4,
                pointHoverRadius: 6,
                pointBackgroundColor: colors.primary,
                pointBorderColor: '#fff',
                pointBorderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Tendencia de Asistencia Mensual',
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: {
                        size: 14
                    },
                    bodyFont: {
                        size: 13
                    },
                    callbacks: {
                        label: function (context) {
                            return 'Asistencias: ' + context.parsed.y;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        precision: 0
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Department Comparison Chart
function createDepartmentComparisonChart(canvas) {
    const ctx = canvas.getContext('2d');

    const labels = JSON.parse(canvas.dataset.labels || '["Administración", "Operaciones", "Finanzas", "RRHH"]');
    const data = JSON.parse(canvas.dataset.values || '[85, 92, 78, 95]');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: '% Asistencia',
                data: data,
                backgroundColor: [
                    colors.primary,
                    colors.success,
                    colors.info,
                    colors.warning
                ],
                borderRadius: 8,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Asistencia por Departamento',
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    callbacks: {
                        label: function (context) {
                            return 'Asistencia: ' + context.parsed.y + '%';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        callback: function (value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Late Arrivals Pie Chart
function createLateArrivalsChart(canvas) {
    const ctx = canvas.getContext('2d');

    const onTime = parseInt(canvas.dataset.ontime || '80');
    const late = parseInt(canvas.dataset.late || '15');
    const absent = parseInt(canvas.dataset.absent || '5');

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['A Tiempo', 'Tarde', 'Ausente'],
            datasets: [{
                data: [onTime, late, absent],
                backgroundColor: [
                    colors.success,
                    colors.warning,
                    colors.danger
                ],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: {
                            size: 12
                        }
                    }
                },
                title: {
                    display: true,
                    text: 'Puntualidad Hoy',
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    callbacks: {
                        label: function (context) {
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            return context.label + ': ' + context.parsed + ' (' + percentage + '%)';
                        }
                    }
                }
            }
        }
    });
}

// Weekly Heatmap Chart (using bar chart)
function createWeeklyHeatmapChart(canvas) {
    const ctx = canvas.getContext('2d');

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: ['Lun', 'Mar', 'Mié', 'Jue', 'Vie'],
            datasets: [{
                label: 'Asistencias',
                data: [92, 88, 95, 90, 85],
                backgroundColor: function (context) {
                    const value = context.parsed.y;
                    if (value >= 90) return colors.success;
                    if (value >= 80) return colors.warning;
                    return colors.danger;
                },
                borderRadius: 8,
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                title: {
                    display: true,
                    text: 'Asistencia Semanal',
                    font: {
                        size: 16,
                        weight: 'bold'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    callbacks: {
                        label: function (context) {
                            return 'Asistencias: ' + context.parsed.y + '%';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    max: 100,
                    grid: {
                        color: 'rgba(0, 0, 0, 0.05)'
                    },
                    ticks: {
                        callback: function (value) {
                            return value + '%';
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    }
                }
            }
        }
    });
}

// Utility function to update chart data dynamically
function updateChartData(chartId, newLabels, newData) {
    const canvas = document.getElementById(chartId);
    if (canvas && canvas.chart) {
        canvas.chart.data.labels = newLabels;
        canvas.chart.data.datasets[0].data = newData;
        canvas.chart.update();
    }
}

// Export chart as image
function exportChartAsImage(chartId, filename) {
    const canvas = document.getElementById(chartId);
    if (canvas) {
        const url = canvas.toDataURL('image/png');
        const link = document.createElement('a');
        link.download = filename || 'chart.png';
        link.href = url;
        link.click();
    }
}
