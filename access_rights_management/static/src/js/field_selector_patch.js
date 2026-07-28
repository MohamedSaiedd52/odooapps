/** @odoo-module **/
import { ModelFieldSelectorPopover } from "@web/core/model_field_selector/model_field_selector_popover";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";

patch(ModelFieldSelectorPopover.prototype, {
    setup() {
        super.setup();
        this.armOrm = useService("orm");
    },
    async loadPages(resModel, path) {
        const page = await super.loadPages(...arguments);
        try {
            const hidden = await this.armOrm.call(
                "access.rights.profile",
                "get_hidden_fields",
                [resModel]
            );
            if (hidden.length) {
                page.fieldNames = page.fieldNames.filter((name) => !hidden.includes(name));
                page.sortedFieldNames = page.sortedFieldNames.filter(
                    (name) => !hidden.includes(name)
                );
                if (hidden.includes(page.selectedName)) {
                    page.selectedName = "";
                }
            }
        } catch {
            // never break the field selector
        }
        return page;
    },
});
