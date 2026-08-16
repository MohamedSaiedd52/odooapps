/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, onPatched } from "@odoo/owl";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";

// Global chart instances for analytics
let analyticsChartInstances = new Map();

/**
 * Initialize Analytics Charts when form view loads
 */
function initAnalyticsCharts(orm, resId) {
    if (!resId) return;

    console.log("Initializing analytics charts for record:", resId);

    // Fetch chart data
    orm.call("shopify.analytics", "read", [[resId], [
        "sales_chart_data",
        "customer_chart_data",
        "product_chart_data",
        "inventory_chart_data"
    ]]).then(result => {
        if (result && result.length > 0) {
            const data = result[0];
            console.log("Fetched chart data:", data);

            // Wait for DOM to be fully ready
            setTimeout(() => {
                renderAnalyticsCharts(data);
            }, 800);
        }
    }).catch(err => {
        console.error("Error fetching chart data:", err);
    });
}

/**
 * Render all analytics charts
 */
function renderAnalyticsCharts(data) {
    // Check if Chart.js is available
    if (typeof Chart === 'undefined') {
        console.error("Chart.js is not loaded!");
        return;
    }

    console.log("Rendering analytics charts...");

    // Destroy existing charts
    analyticsChartInstances.forEach(chart => chart.destroy());
    analyticsChartInstances.clear();

    // Render each chart
    renderSalesChart(data.sales_chart_data);
    renderCustomerChart(data.customer_chart_data);
    renderProductChart(data.product_chart_data);
    renderInventoryChart(data.inventory_chart_data);
}

function renderSalesChart(chartData) {
    const canvas = document.getElementById('analytics_sales_chart');
    if (!canvas) {
        console.log("Sales chart canvas not found");
        return;
    }

    const data = chartData || { labels: ['No Data'], values: [0] };
    console.log("Rendering sales chart with data:", data);

    const chart = new Chart(canvas, {
        type: 'line',
        data: {
            labels: data.labels && data.labels.length ? data.labels : ['No Data'],
            datasets: [{
                label: 'Sales (SAR)',
                data: data.values && data.values.length ? data.values : [0],
                borderColor: '#8b5cf6',
                backgroundColor: 'rgba(139, 92, 246, 0.2)',
                borderWidth: 3,
                fill: true,
                tension: 0.4,
                pointRadius: 5,
                pointBackgroundColor: '#8b5cf6'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top' },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const value = context.raw || 0;
                            return `Sales: ${value.toLocaleString('en-SA')} SAR`;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0, 0, 0, 0.1)' },
                    ticks: {
                        color: '#374151',
                        callback: function(value) {
                            return value.toLocaleString('en-SA') + ' SAR';
                        }
                    }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#374151' }
                }
            }
        }
    });

    analyticsChartInstances.set('sales', chart);
}

function renderCustomerChart(chartData) {
    const canvas = document.getElementById('analytics_customer_chart');
    if (!canvas) {
        console.log("Customer chart canvas not found");
        return;
    }

    const data = chartData || { labels: ['No Data'], values: [0] };

    const chart = new Chart(canvas, {
        type: 'bar',
        data: {
            labels: data.labels && data.labels.length ? data.labels : ['No Data'],
            datasets: [{
                label: 'New Customers',
                data: data.values && data.values.length ? data.values : [0],
                backgroundColor: '#4ade80',
                borderRadius: 8,
                barThickness: 40
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: true, position: 'top' }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: { color: 'rgba(0, 0, 0, 0.1)' },
                    ticks: { color: '#374151' }
                },
                x: {
                    grid: { display: false },
                    ticks: { color: '#374151' }
                }
            }
        }
    });

    analyticsChartInstances.set('customer', chart);
}

function renderProductChart(chartData) {
    const canvas = document.getElementById('analytics_product_chart');
    if (!canvas) {
        console.log("Product chart canvas not found");
        return;
    }

    const data = chartData || { labels: [], values: [] };

    // Check if we have real data
    if (!data.labels || !data.labels.length || !data.values || !data.values.length) {
        // Show "No Data" message instead of chart
        const container = canvas.parentElement;
        if (container) {
            container.innerHTML = `
                <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100%; color: #6b7280;">
                    <i class="fa fa-pie-chart" style="font-size: 48px; margin-bottom: 10px; opacity: 0.5;"></i>
                    <p style="margin: 0; font-size: 14px;">No product sales data available</p>
                    <p style="margin: 5px 0 0 0; font-size: 12px; opacity: 0.7;">Sync order line items to see product analytics</p>
                </div>
            `;
        }
        return;
    }

    const chart = new Chart(canvas, {
        type: 'pie',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.values,
                backgroundColor: [
                    '#8b5cf6', '#4ade80', '#f59e0b', '#ef4444', '#3b82f6',
                    '#ec4899', '#14b8a6', '#f97316', '#6366f1', '#84cc16'
                ],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            layout: {
                padding: 10
            },
            plugins: {
                legend: {
                    position: 'right',
                    align: 'center',
                    labels: {
                        color: '#374151',
                        padding: 8,
                        usePointStyle: true,
                        font: { size: 10 },
                        boxWidth: 12
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            // Format as currency (SAR)
                            return `${label}: ${value.toLocaleString('en-SA')} SAR`;
                        }
                    }
                }
            }
        }
    });

    analyticsChartInstances.set('product', chart);
}

function renderInventoryChart(chartData) {
    const canvas = document.getElementById('analytics_inventory_chart');
    if (!canvas) {
        console.log("Inventory chart canvas not found");
        return;
    }

    const data = chartData || { labels: ['In Stock', 'Low Stock', 'Out of Stock'], values: [0, 0, 0] };

    const chart = new Chart(canvas, {
        type: 'doughnut',
        data: {
            labels: data.labels || ['In Stock', 'Low Stock', 'Out of Stock'],
            datasets: [{
                data: data.values || [0, 0, 0],
                backgroundColor: ['#10b981', '#f59e0b', '#ef4444'],
                borderWidth: 2,
                borderColor: '#ffffff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { color: '#374151', padding: 15, usePointStyle: true }
                }
            }
        }
    });

    analyticsChartInstances.set('inventory', chart);
}

/**
 * Patch FormController to initialize charts for shopify.analytics model
 */
patch(FormController.prototype, {
    setup() {
        super.setup();

        // Check if this is the shopify.analytics model
        if (this.props.resModel === 'shopify.analytics') {
            console.log("Analytics form detected");
        }
    },

    async onRecordSaved(record) {
        await super.onRecordSaved?.(record);

        // Re-initialize charts after save
        if (this.props.resModel === 'shopify.analytics') {
            const resId = this.model.root?.resId;
            if (resId) {
                setTimeout(() => {
                    initAnalyticsCharts(this.orm, resId);
                }, 500);
            }
        }
    }
});

/**
 * MutationObserver to detect when analytics form is loaded and render charts
 */
let observerInitialized = false;

function setupAnalyticsObserver() {
    if (observerInitialized) return;
    observerInitialized = true;

    const observer = new MutationObserver((mutations) => {
        const analyticsForm = document.querySelector('.o_shopify_analytics_dashboard');
        if (analyticsForm && !analyticsForm.dataset.chartsInitialized) {
            analyticsForm.dataset.chartsInitialized = 'true';
            console.log("Analytics form detected via MutationObserver");

            // Get record ID from URL
            const urlMatch = window.location.hash.match(/id=(\d+)/);
            const resId = urlMatch ? parseInt(urlMatch[1]) : null;

            if (resId) {
                // Use rpc to fetch data
                const orm = {
                    call: (model, method, args) => {
                        return fetch('/web/dataset/call_kw/' + model + '/' + method, {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json',
                            },
                            body: JSON.stringify({
                                jsonrpc: '2.0',
                                method: 'call',
                                params: {
                                    model: model,
                                    method: method,
                                    args: args,
                                    kwargs: {}
                                },
                                id: Math.floor(Math.random() * 1000000)
                            })
                        }).then(r => r.json()).then(r => r.result);
                    }
                };

                setTimeout(() => {
                    initAnalyticsCharts(orm, resId);
                }, 1000);
            }
        }
    });

    observer.observe(document.body, { childList: true, subtree: true });
}

// Setup observer when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', setupAnalyticsObserver);
} else {
    setupAnalyticsObserver();
}

/**
 * Analytics Charts Widget - For field-based rendering
 */
class AnalyticsChartsWidget extends Component {
    static template = "ms_shopify_automation.AnalyticsChartsWidget";
    static props = { ...standardFieldProps };

    setup() {
        this.orm = useService("orm");

        onMounted(() => {
            console.log("Analytics Charts Widget Mounted");
            this.initCharts();
        });

        onPatched(() => {
            console.log("Analytics Charts Widget Patched");
            this.initCharts();
        });
    }

    async initCharts() {
        const record = this.props.record;
        if (record?.resId) {
            initAnalyticsCharts(this.orm, record.resId);
        }
    }
}

// Register as a field widget
registry.category("fields").add("analytics_charts", {
    component: AnalyticsChartsWidget,
});

export default AnalyticsChartsWidget;
