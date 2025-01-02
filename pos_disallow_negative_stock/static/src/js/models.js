/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { Order } from "@point_of_sale/app/store/models";
import { _t } from "@web/core/l10n/translation";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";

patch(Order.prototype, {
    async pay() {
        let order_json = this.export_as_JSON();
        const res = await this.env.services.orm.call(
            "pos.order",
            "check_order_qty",
            [order_json]
        )
        if (res){
            this.env.services.popup.add(ErrorPopup, {
                title: _t("Zero Quantity Not Allowed"),
                body: res.message,
            });
            return false;
        }
        return super.pay(...arguments);
    }
});