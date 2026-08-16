/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onWillStart, useState, onWillUnmount } from "@odoo/owl";

export class ShopifyAutomationDashboard extends Component {
    static template = "ms_shopify_automation.ShopifyAutomationDashboard";
    static props = { "*": true };

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");

        this.state = useState({
            loading: true,
            error: null,
            hasConnectedInstance: false,
            instanceData: null,
            dashboardData: {
                total_sales: 0,
                order_count: 0,
                customer_count: 0,
                product_count: 0,
                queue_job_count: 0,
                error_count: 0,
                sales_chart_data: { labels: [], values: [] },
                customer_growth: [],
                customer_growth_labels: [],
                inventory_status: [0, 0, 0],
                revenue_distribution: [0, 0, 0],
            },
        });

        this.chartInstances = new Map();
        this.updateInterval = null;

        onWillStart(async () => {
            await this.loadDashboardData();
        });

        onMounted(() => {
            if (this.state.hasConnectedInstance && !this.state.error) {
                this.initializeCharts();
                this.startAutoRefresh();
            }
        });

        onWillUnmount(() => {
            this.stopAutoRefresh();
            this.destroyCharts();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        this.state.error = null;

        try {
            // Check if there's a connected instance
            const instances = await this.orm.searchRead(
                "shopify.instance",
                [["state", "=", "connected"], ["active", "=", true]],
                ["id", "name", "shop_url", "last_sync", "state"],
                { limit: 1 }
            );

            if (instances.length === 0) {
                this.state.hasConnectedInstance = false;
                this.state.loading = false;
                return;
            }

            this.state.instanceData = instances[0];
            this.state.hasConnectedInstance = true;

            // Load dashboard KPIs and chart data
            const dashboardData = await this.orm.call(
                "shopify.instance",
                "get_dashboard_data",
                []
            );

            this.state.dashboardData = {
                ...this.state.dashboardData,
                ...dashboardData
            };

        } catch (error) {
            console.error("Failed to load dashboard data:", error);
            this.state.error = error.message || "Failed to load dashboard data";
            this.notification.add(this.state.error, { type: "danger" });
        } finally {
            this.state.loading = false;
        }
    }

    startAutoRefresh() {
        // Refresh data every 60 seconds
        this.updateInterval = setInterval(() => {
            this.refreshData();
        }, 60000);
    }

    stopAutoRefresh() {
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }
    }

    destroyCharts() {
        this.chartInstances.forEach(chart => {
            if (chart && typeof chart.destroy === 'function') {
                chart.destroy();
            }
        });
        this.chartInstances.clear();
    }

    async refreshData() {
        if (!this.state.hasConnectedInstance) return;

        try {
            const dashboardData = await this.orm.call(
                "shopify.instance",
                "get_dashboard_data",
                []
            );
            this.state.dashboardData = {
                ...this.state.dashboardData,
                ...dashboardData
            };
            this.updateCharts(dashboardData);
        } catch (error) {
            console.error("Failed to refresh data:", error);
        }
    }

    // Navigation methods
    navigateToCreateInstance() {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "shopify.instance",
            view_mode: "form",
            views: [[false, "form"]],
            target: "current",
        });
    }

    navigateToInstances() {
        this.action.doAction("ms_shopify_automation.action_shopify_instance");
    }

    navigateToOrders() {
        this.action.doAction("ms_shopify_automation.action_shopify_order");
    }

    navigateToProducts() {
        this.action.doAction("ms_shopify_automation.action_shopify_product");
    }

    navigateToCustomers() {
        this.action.doAction("ms_shopify_automation.action_shopify_customer");
    }

    navigateToQueueJobs() {
        this.action.doAction("ms_shopify_automation.action_shopify_queue_job");
    }

    navigateToLogs() {
        this.action.doAction("ms_shopify_automation.action_shopify_log");
    }

    navigateToCronJobs() {
        this.action.doAction("ms_shopify_automation.action_shopify_cron");
    }

    navigateToWebhooks() {
        this.action.doAction("ms_shopify_automation.action_shopify_webhook");
    }

    // Chart methods
    initializeCharts() {
        // Wait for DOM to be ready
        setTimeout(() => {
            this.initializeSalesChart();
            this.initializeRevenueChart();
            this.initializeCustomerChart();
            this.initializeInventoryChart();
        }, 100);
    }

    initializeSalesChart() {
        const ctx = document.getElementById('dashboard_sales_chart');
        if (!ctx || typeof Chart === 'undefined') return;

        const data = this.state.dashboardData.sales_chart_data || { labels: [], values: [] };

        const chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels || [],
                datasets: [{
                    label: 'Sales',
                    data: data.values || [],
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
                        grid: { color: 'rgba(0, 0, 0, 0.1)' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });

        this.chartInstances.set('sales', chart);
    }

    initializeRevenueChart() {
        const ctx = document.getElementById('dashboard_revenue_chart');
        if (!ctx || typeof Chart === 'undefined') return;

        const data = this.state.dashboardData.revenue_distribution || [65, 25, 10];

        const chart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: ['Online Sales', 'In-Store Sales', 'Wholesale'],
                datasets: [{
                    data: data,
                    backgroundColor: ['#667eea', '#764ba2', '#f093fb'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });

        this.chartInstances.set('revenue', chart);
    }

    initializeCustomerChart() {
        const ctx = document.getElementById('dashboard_customer_chart');
        if (!ctx || typeof Chart === 'undefined') return;

        const labels = this.state.dashboardData.customer_growth_labels || ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'];
        const data = this.state.dashboardData.customer_growth || [120, 150, 180, 200, 220, 250];

        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [{
                    label: 'New Customers',
                    data: data,
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
                        grid: { color: 'rgba(0, 0, 0, 0.1)' }
                    },
                    x: {
                        grid: { display: false }
                    }
                }
            }
        });

        this.chartInstances.set('customer', chart);
    }

    initializeInventoryChart() {
        const ctx = document.getElementById('dashboard_inventory_chart');
        if (!ctx || typeof Chart === 'undefined') return;

        const data = this.state.dashboardData.inventory_status || [70, 20, 10];

        const chart = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: ['In Stock', 'Low Stock', 'Out of Stock'],
                datasets: [{
                    data: data,
                    backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });

        this.chartInstances.set('inventory', chart);
    }

    updateCharts(data) {
        // Update sales chart
        const salesChart = this.chartInstances.get('sales');
        if (salesChart && data.sales_chart_data) {
            salesChart.data.labels = data.sales_chart_data.labels;
            salesChart.data.datasets[0].data = data.sales_chart_data.values;
            salesChart.update('none');
        }

        // Update revenue chart
        const revenueChart = this.chartInstances.get('revenue');
        if (revenueChart && data.revenue_distribution) {
            revenueChart.data.datasets[0].data = data.revenue_distribution;
            revenueChart.update('none');
        }

        // Update customer chart
        const customerChart = this.chartInstances.get('customer');
        if (customerChart && data.customer_growth) {
            if (data.customer_growth_labels) {
                customerChart.data.labels = data.customer_growth_labels;
            }
            customerChart.data.datasets[0].data = data.customer_growth;
            customerChart.update('none');
        }

        // Update inventory chart
        const inventoryChart = this.chartInstances.get('inventory');
        if (inventoryChart && data.inventory_status) {
            inventoryChart.data.datasets[0].data = data.inventory_status;
            inventoryChart.update('none');
        }
    }

    formatCurrency(value) {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2
        }).format(value || 0);
    }

    formatNumber(value) {
        return new Intl.NumberFormat('en-US').format(value || 0);
    }
}

// Register with the NEW tag name matching XML
registry.category("actions").add("shopify_automation_dashboard", ShopifyAutomationDashboard);

export default ShopifyAutomationDashboard;
