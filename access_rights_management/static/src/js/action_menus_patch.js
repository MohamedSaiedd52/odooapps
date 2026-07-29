/** @odoo-module **/
import { ActionMenus } from "@web/search/action_menus/action_menus";
import { patch } from "@web/core/utils/patch";

patch(ActionMenus.prototype, {
    async getActionItems(props) {
        const items = await super.getActionItems(props);
        if (!items.length || !props.resModel) {
            return items;
        }
        try {
            const removed = await this.orm.call(
                "access.rights.profile",
                "get_removed_action_options",
                [props.resModel]
            );
            if (removed.length) {
                return items.filter((item) => !removed.includes(item.key));
            }
        } catch {
            // never break the UI because of the access check
        }
        return items;
    },
});
