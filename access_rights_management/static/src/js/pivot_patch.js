/** @odoo-module **/
/**
 * Hide the fields a profile makes invisible from the pivot group-by dropdown.
 *
 * 19.0 dropped `@web/views/pivot/pivot_header` and moved the field list that
 * feeds that dropdown into `PivotRenderer` (18.0 had it on `PivotHeader`).
 *
 * The file still lives in `web.assets_backend_lazy`, not in
 * `web.assets_backend`: the pivot and graph views are served on demand, so a
 * file importing from them out of an eagerly-loaded bundle would stay
 * undefined for the whole session.
 */
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart } from "@odoo/owl";

import { armFilterFields } from "@access_rights_management/js/search_menu_patch";

patch(PivotRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        this.armOrm = useService("orm");
        onWillStart(() =>
            armFilterFields(this, this.env.searchModel && this.env.searchModel.resModel)
        );
    },
});
