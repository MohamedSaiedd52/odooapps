/** @odoo-module **/
import { SearchBarMenu } from "@web/search/search_bar_menu/search_bar_menu";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

/**
 * Drop the fields a profile hides from a component that offers them for
 * filtering or grouping.
 *
 * Exported because the pivot renderer needs it too, and the pivot and graph
 * views are served from a lazy bundle: importing from them here would leave
 * this whole module undefined on every page. See js/pivot_patch.js.
 */
export function armFilterFields(component, resModel) {
    if (!resModel || !Array.isArray(component.fields)) {
        return Promise.resolve();
    }
    return component.armOrm
        .call("access.rights.profile", "get_hidden_fields", [resModel])
        .then((hidden) => {
            if (hidden.length) {
                component.fields = component.fields.filter(
                    (field) => !hidden.includes(field.name)
                );
            }
        })
        .catch(() => {});
}

patch(SearchBarMenu.prototype, {
    setup() {
        super.setup(...arguments);
        this.armOrm = useService("orm");
        onWillStart(() =>
            armFilterFields(this, this.env.searchModel && this.env.searchModel.resModel)
        );
    },
});
