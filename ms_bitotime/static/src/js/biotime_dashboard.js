/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { Component, onMounted, useRef, useState } from "@odoo/owl";

const actionRegistry = registry.category("actions");

class BiotimeDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.state = useState({
            devices: 0,
            employees: 0,
            attendance: 0,
            chartLabels: [],
            chartData: [],
        });

        // Create a ref for canvas
        this.canvasRef = useRef("attendanceChart");

        onMounted(() => {
            this.loadData();
        });
    }

    async loadData() {
        // Tiles
        const result = await this.orm.call("biotime.dashboard", "get_dashboard_data", [], {});
        this.state.devices = result.devices;
        this.state.employees = result.employees;
        this.state.attendance = result.attendance;

        // Chart
        const chartResult = await this.orm.call("biotime.dashboard", "get_weekly_attendance", [], {});
        this.state.chartLabels = chartResult.labels;
        this.state.chartData = chartResult.data;

        this.renderChart();
    }

    renderChart() {
        const ctx = this.canvasRef.el;   // safe access to <canvas>
        if (!ctx) return;

        if (this.chart) {
            this.chart.destroy();
        }

        this.chart = new Chart(ctx, {
            type: "bar",
            data: {
                labels: this.state.chartLabels,
                datasets: [
                    {
                        label: "Attendance (Last 7 Days)",
                        data: this.state.chartData,
                        backgroundColor: "rgba(54, 162, 235, 0.6)",
                        borderColor: "rgba(54, 162, 235, 1)",
                        borderWidth: 1,
                    },
                ],
            },
            options: {
                responsive: true,
                scales: {
                    y: { beginAtZero: true },
                },
            },
        });
    }
}

BiotimeDashboard.template = "ms_bitotime.Template";
actionRegistry.add("ms_bitotime_tag", BiotimeDashboard);
