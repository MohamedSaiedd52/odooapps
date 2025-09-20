/** @odoo-module **/
import { registry } from "@web/core/registry";
import { Component, onWillStart, xml, useEffect } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class ReportBackend extends Component {
    setup() {
        this.actionService = useService("action");
        this.orm = useService("orm");
        this.id = this.props.action.context.active_id;
        this.html = null;

        onWillStart(this.onWillStart.bind(this));

        useEffect(
            (el) => {
                if (!el || !this.html) {
                    return;
                }

                // Parse the HTML content and attach event listeners
                const container = document.createElement("div");
                container.innerHTML = this.html;

                container.querySelector('.o_stock_card_report_aas_print')?.addEventListener("click", () => {
                    this.print();
                });

                container.querySelector('.o_stock_card_report_aas_export')?.addEventListener("click", () => {
                    this.export();
                });

                // Append the content to the DOM
                el.innerHTML = ""; // Clear previous content
                el.appendChild(container);
            },
            () => [document.querySelector(".report_container")],
        );
    }

    async print() {
        const result = await this.orm.call(
            this.props.action.context.active_model,
            "print_report",
            [this.id],
            { context: this.props.action.context, mode: "qweb-pdf" }
        );
        this.actionService.doAction(result);
    }

    async export() {
        const result = await this.orm.call(
            this.props.action.context.active_model,
            "print_report",
            [this.id],
            { context: this.props.action.context, mode: "xlsx" }
        );
        this.actionService.doAction(result);
    }

    async onWillStart() {
        await this.getHtml();
    }

    async getHtml() {
        const result = await this.orm.call(
            this.props.action.context.active_model,
            "get_html",
            [],
            { context: this.props.action.context }
        );
        this.html = result.html;
    }
}

ReportBackend.template = xml`<div class="report_container"></div>`;
registry.category("actions").add("stock_card_report_aa_backend", ReportBackend);


