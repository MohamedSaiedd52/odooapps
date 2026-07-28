/** @odoo-module **/
/**
 * Export audit — tell the audit log *where* an export came from.
 *
 * The payload the web client posts to /web/export/* carries the model, the
 * domain and the exported columns, but nothing about the screen the user was
 * standing on, nor the saved export template they picked. Both are known
 * here, so they travel with the request in an `arm_origin` block. Everything
 * in that block is browser input: the server validates each reference before
 * storing it (see models/security_audit.py, `_origin_values`).
 */
import { _t } from "@web/core/l10n/translation";
import { download } from "@web/core/network/download";
import { patch } from "@web/core/utils/patch";
import { ListController } from "@web/views/list/list_controller";
import { ExportDataDialog } from "@web/views/view_dialogs/export_data_dialog";

// The dialog knows which template built the field list; the controller owns
// the request. One optional callback carries the answer from one to the other.
ExportDataDialog.props = {
    ...ExportDataDialog.props,
    armSetTemplate: { type: Function, optional: true },
};

patch(ExportDataDialog.prototype, {
    async onClickExportButton() {
        const templateId = Number(this.state.templateId);
        const template = this.templates.find((t) => t.id === templateId);
        this.props.armSetTemplate?.(
            template ? { id: template.id, name: template.name } : false
        );
        return super.onClickExportButton(...arguments);
    },
});

patch(ListController.prototype, {
    async onExportData() {
        this.armExportTemplate = false;
        this.dialogService.add(ExportDataDialog, {
            context: this.props.context,
            defaultExportList: this.defaultExportList,
            download: this.downloadExport.bind(this),
            getExportedFields: this.getExportedFields.bind(this),
            root: this.model.root,
            armSetTemplate: (template) => {
                this.armExportTemplate = template;
            },
        });
    },

    async onDirectExportData() {
        // "Export All" straight from the cog menu: default columns, no template
        this.armExportTemplate = false;
        return super.onDirectExportData(...arguments);
    },

    /**
     * Mirrors the core 17.0 `downloadExport` and adds `arm_origin`. Core reads
     * the payload key by key and ignores the ones it does not know, so a
     * version drift here can only ever cost the audit its extra detail — never
     * the download itself.
     */
    async downloadExport(fields, import_compat, format) {
        let ids = false;
        if (!this.isDomainSelected) {
            const resIds = await this.getSelectedResIds();
            ids = resIds.length > 0 && resIds;
        }
        const exportedFields = fields.map((field) => ({
            name: field.name || field.id,
            label: field.label || field.string,
            store: field.store,
            type: field.field_type || field.type,
        }));
        if (import_compat) {
            exportedFields.unshift({ name: "id", label: _t("External ID") });
        }
        const template = this.armExportTemplate;
        await download({
            data: {
                data: JSON.stringify({
                    import_compat,
                    context: this.props.context,
                    domain: this.model.root.domain,
                    fields: exportedFields,
                    groupby: this.model.root.groupBy,
                    ids,
                    model: this.model.root.resModel,
                    arm_origin: {
                        action_id: this.env.config.actionId || false,
                        screen_name: this.armScreenName(),
                        view_type: this.env.config.viewType || "list",
                        template_id: template ? template.id : false,
                        template_name: template ? template.name : "",
                        scope: ids ? "selected" : "filtered",
                        import_compat,
                    },
                }),
            },
            url: `/web/export/${format}`,
        });
    },

    /** The screen as the user sees it named in the breadcrumb. */
    armScreenName() {
        const config = this.env.config;
        try {
            return (config.getDisplayName && config.getDisplayName()) || config.actionName || "";
        } catch {
            return "";
        }
    },
});
