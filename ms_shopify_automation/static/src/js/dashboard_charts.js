/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillUnmount, useState } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

/**
 * Dashboard Charts Widget - Renders charts in the form view
 * This widget initializes Chart.js charts when the form view loads
 */
class DashboardChartsWidget extends Component {
    static template = "ms_shopify_automation.DashboardChartsWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");
        this.chartInstances = new Map();
        this.state = useState({
            loading: true,
            chartData: null,
        });

        onMounted(() => {
            this.loadAndRenderCharts();
        });

        onWillUnmount(() => {
            this.destroyCharts();
        });
    }

    async loadAndRenderCharts() {
        try {
            // Get chart data from the server
            const data = await this.orm.call(
                "shopify.instance",
                "get_dashboard_data",
                []
            );

            this.state.chartData = data;
            this.state.loading = false;

            // Wait for DOM to be ready then render charts
            setTimeout(() => {
                this.renderAllCharts(data);
            }, 100);
        } catch (error) {
            console.error("Failed to load chart data:", error);
            this.state.loading = false;
        }
    }

    renderAllCharts(data) {
        this.renderSalesChart(data);
        this.renderRevenueChart(data);
        this.renderCustomerChart(data);
        this.renderInventoryChart(data);
    }

    renderSalesChart(data) {
        const canvas = document.getElementById('sales_chart_canvas');
        if (!canvas || typeof Chart === 'undefined') return;

        // Destroy existing chart if any
        if (this.chartInstances.has('sales')) {
            this.chartInstances.get('sales').destroy();
        }

        const chartData = data.sales_chart_data || { labels: [], values: [] };

        const chart = new Chart(canvas, {
            type: 'line',
            data: {
                labels: chartData.labels || [],
                datasets: [{
                    label: 'Sales',
                    data: chartData.values || [],
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: '#a0aec0' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#a0aec0' }
                    }
                }
            }
        });

        this.chartInstances.set('sales', chart);
    }

    renderRevenueChart(data) {
        const canvas = document.getElementById('revenue_chart_canvas');
        if (!canvas || typeof Chart === 'undefined') return;

        if (this.chartInstances.has('revenue')) {
            this.chartInstances.get('revenue').destroy();
        }

        const revenueData = data.revenue_distribution || [70, 20, 10];

        const chart = new Chart(canvas, {
            type: 'doughnut',
            data: {
                labels: ['Online Sales', 'Wholesale', 'Other'],
                datasets: [{
                    data: revenueData,
                    backgroundColor: ['#667eea', '#764ba2', '#f093fb'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#a0aec0' }
                    }
                }
            }
        });

        this.chartInstances.set('revenue', chart);
    }

    renderCustomerChart(data) {
        const canvas = document.getElementById('customer_chart_canvas');
        if (!canvas || typeof Chart === 'undefined') return;

        if (this.chartInstances.has('customer')) {
            this.chartInstances.get('customer').destroy();
        }

        const customerData = data.customer_growth || [];
        const customerLabels = data.customer_growth_labels || [];

        const chart = new Chart(canvas, {
            type: 'bar',
            data: {
                labels: customerLabels,
                datasets: [{
                    label: 'New Customers',
                    data: customerData,
                    backgroundColor: '#8b5cf6',
                    borderRadius: 8
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255, 255, 255, 0.1)' },
                        ticks: { color: '#a0aec0' }
                    },
                    x: {
                        grid: { display: false },
                        ticks: { color: '#a0aec0' }
                    }
                }
            }
        });

        this.chartInstances.set('customer', chart);
    }

    renderInventoryChart(data) {
        const canvas = document.getElementById('inventory_chart_canvas');
        if (!canvas || typeof Chart === 'undefined') return;

        if (this.chartInstances.has('inventory')) {
            this.chartInstances.get('inventory').destroy();
        }

        const inventoryData = data.inventory_status || [70, 20, 10];

        const chart = new Chart(canvas, {
            type: 'pie',
            data: {
                labels: ['In Stock', 'Low Stock', 'Out of Stock'],
                datasets: [{
                    data: inventoryData,
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#a0aec0' }
                    }
                }
            }
        });

        this.chartInstances.set('inventory', chart);
    }

    destroyCharts() {
        this.chartInstances.forEach(chart => {
            chart.destroy();
        });
        this.chartInstances.clear();
    }
}

DashboardChartsWidget.template = "ms_shopify_automation.DashboardChartsWidget";

// Register as a field widget
registry.category("fields").add("dashboard_charts", {
    component: DashboardChartsWidget,
});

export default DashboardChartsWidget;
