/**
 * Reports Module
 * Handles charts and statistics
 */

const ReportsModule = {
    // ============ State ============
    currentPeriod: 'month',
    chart: null,
    
    // ============ Init ============
    init: function() {
        this.loadReport('month');
        this.bindEvents();
    },
    
    // ============ Load Report ============
    loadReport: function(period) {
        this.currentPeriod = period;
        
        $.get(`/admin/api/reports?period=${period}`, (data) => {
            this.updateStats(data.stats);
            this.renderChart(data.chart_data);
        }).fail(() => {
            showToast('خطا در بارگذاری گزارشات', 'error');
        });
    },
    
    // ============ Render Chart ============
    renderChart: function(data) {
        const ctx = document.getElementById('salesChart').getContext('2d');
        
        if (this.chart) {
            this.chart.destroy();
        }
        
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [
                    {
                        label: 'فروش',
                        data: data.sales || [],
                        borderColor: '#3498db',
                        backgroundColor: 'rgba(52, 152, 219, 0.1)',
                        fill: true,
                        tension: 0.4
                    },
                    {
                        label: 'کاربران جدید',
                        data: data.users || [],
                        borderColor: '#2ecc71',
                        backgroundColor: 'rgba(46, 204, 113, 0.1)',
                        fill: true,
                        tension: 0.4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                        rtl: true
                    }
                },
                scales: {
                    x: {
                        grid: {
                            display: false
                        }
                    },
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    },
    
    // ============ Update Stats ============
    updateStats: function(stats) {
        $('#totalSales').text(stats.total_sales || 0);
        $('#totalRevenue').text(stats.total_revenue?.toLocaleString() || 0);
        $('#newUsers').text(stats.new_users || 0);
    },
    
    // ============ Bind Events ============
    bindEvents: function() {
        $('[data-period]').on('click', function() {
            const period = $(this).data('period');
            
            // Update button styles
            $('[data-period]').removeClass('btn-primary').addClass('btn-outline-primary');
            $(this).removeClass('btn-outline-primary').addClass('btn-primary');
            
            ReportsModule.loadReport(period);
        });
    }
};

// ============ Init on DOM Ready ============
$(document).ready(() => {
    ReportsModule.init();
});