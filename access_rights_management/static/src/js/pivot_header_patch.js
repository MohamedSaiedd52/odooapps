/** @odoo-module **/
/**
 * Hide the fields a profile makes invisible from the pivot header dropdown
 * (18.0 folded the old PivotGroupByMenu into it).
 *
 * This patch lives in `web.assets_backend_lazy`, not in `web.assets_backend`:
 * 18.0 removed `web/static/src/views/pivot/**` from the main backend bundle
 * and serves it on demand, so importing PivotHeader from an eagerly-loaded
 * file leaves that file undefined for the whole session.
 */
import { PivotHeader } from "@web/views/pivot/pivot_header";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

import { armFilterFields } from "@access_rights_management/js/search_menu_patch";

patch(PivotHeader.prototype, {
    setup() {
        super.setup(...arguments);
        this.armOrm = useService("orm");
        onWillStart(() =>
            armFilterFields(this, this.env.searchModel && this.env.searchModel.resModel)
        );
    },
});
