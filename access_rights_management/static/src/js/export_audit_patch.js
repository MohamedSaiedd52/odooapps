/** @odoo-module **/
/**
 * Export audit — tell the audit log *where* an export came from.
 *
 * The payload the web client posts to /web/export/* carries the model, the
 * domain and the exported columns, but nothing about the screen the user was
 * standing on, nor the saved export template they picked. Both are known in
 * the client, so they travel with the request in an `arm_origin` block.
 * Everything in that block is browser input: the server validates every
 * reference before storing it (see models/security_audit.py, `_origin_values`).
 *
 * 19.0 note
 * ---------
 * 18.0 owned the request in `ListController.downloadExport`, so the block was
 * added by overriding that method. 19.0 moved the whole export flow into the
 * `useExportRecords` hook (@web/views/view_hook), where the download call is a
 * closure — nothing patchable is left on the controller.
 *
 * So the payload is enriched one level lower, on `download._download`, which
 * core exposes as an assignable property precisely so it can be swapped. Both
 * export paths ("Export…" dialog and "Export All") funnel through it, and the
 * screen/template context is recorded by the two components that know it.
 */
import { download } from "@web/core/network/download";
import { patch } from "@web/core/utils/patch";
import { ExportAll } from "@web/views/list/export_all/export_all";
import { ExportDataDialog } from "@web/views/view_dialogs/export_data_dialog";
import { KanbanController } from "@web/views/kanban/kanban_controller";
import { ListController } from "@web/views/list/list_controller";

// Last screen a list/kanban view was rendered on, and the export template the
// user picked in the dialog. Read once, by the download interceptor below.
let armScreen = null;
let armTemplate = false;

function armReadScreen(component) {
    const config = component.env && component.env.config;
    if (!config) {
        return null;
    }
    let screenName = "";
    try {
        screenName = (config.getDisplayName && config.getDisplayName()) || config.actionName || "";
    } catch {
        screenName = config.actionName || "";
    }
    return {
        action_id: config.actionId || false,
        screen_name: screenName,
        view_type: config.viewType || "list",
    };
}

// A fresh object per call: `patch()` rewires the extension's prototype to make
// `super` work, so the same literal must never be handed to two prototypes.
function armRememberScreen() {
    return {
        setup() {
            super.setup(...arguments);
            armScreen = armReadScreen(this) || armScreen;
        },
    };
}

patch(ListController.prototype, armRememberScreen());
patch(KanbanController.prototype, armRememberScreen());

patch(ExportAll.prototype, {
    async onDirectExportData() {
        // straight from the cog menu: default columns, no saved template
        armTemplate = false;
        armScreen = armReadScreen(this) || armScreen;
        return super.onDirectExportData(...arguments);
    },
});

patch(ExportDataDialog.prototype, {
    async onClickExportButton() {
        const templateId = Number(this.state.templateId);
        const template = this.templates.find((t) => t.id === templateId);
        armTemplate = template ? { id: template.id, name: template.name } : false;
        const screen = armReadScreen(this);
        if (screen) {
            armScreen = screen;
        }
        return super.onClickExportButton(...arguments);
    },
});

const armSuperDownload = download._download;
download._download = (options) => {
    try {
        if (options && /^\/web\/export\//.test(options.url || "") && options.data?.data) {
            const payload = JSON.parse(options.data.data);
            payload.arm_origin = {
                ...(armScreen || { action_id: false, screen_name: "", view_type: "list" }),
                template_id: armTemplate ? armTemplate.id : false,
                template_name: armTemplate ? armTemplate.name : "",
                scope: payload.ids ? "selected" : "filtered",
                import_compat: !!payload.import_compat,
            };
            options = { ...options, data: { ...options.data, data: JSON.stringify(payload) } };
        }
    } catch {
        // the audit detail is a bonus: never let it cost the user the download
    }
    return armSuperDownload(options);
};
