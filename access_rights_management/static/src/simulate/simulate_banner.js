/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";
import { useService } from "@web/core/utils/hooks";
import { Component, useState } from "@odoo/owl";

/**
 * Fixed bar shown while an administrator is simulating another user
 * (access.rights.studio.simulate_user). The only way back is this banner:
 * the simulated user usually has no access to the ARM screens.
 */
export class ArmSimulateBanner extends Component {
    static template = "access_rights_management.SimulateBanner";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.info = session.arm_simulate || null;
        this.state = useState({ busy: false });
    }

    async exit() {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            await this.orm.call("access.rights.studio", "simulate_stop", []);
        } finally {
            window.location.href = "/web";
        }
    }
}

registry.category("main_components").add("ArmSimulateBanner", {
    Component: ArmSimulateBanner,
});
