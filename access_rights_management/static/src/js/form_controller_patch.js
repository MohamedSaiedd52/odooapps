/** @odoo-module **/
import { FormController } from "@web/views/form/form_controller";
import { patch } from "@web/core/utils/patch";
import { onWillStart, useState } from "@odoo/owl";

patch(FormController.prototype, {
    setup() {
        super.setup();
        this.armAccess = useState({ hideAddProperty: false });
        onWillStart(async () => {
            try {
                this.armAccess.hideAddProperty = await this.orm.call(
                    "access.rights.profile",
                    "is_add_property_hidden",
                    [this.props.resModel]
                );
            } catch {
                this.armAccess.hideAddProperty = false;
            }
        });
    },
    get actionMenuItems() {
        const menuItems = super.actionMenuItems;
        if (this.armAccess.hideAddProperty && menuItems && menuItems.action) {
            menuItems.action = menuItems.action.filter(
                (item) => item.key !== "addPropertyFieldValue"
            );
        }
        return menuItems;
    },
});
