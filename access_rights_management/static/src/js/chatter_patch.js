/** @odoo-module **/
import { Chatter } from "@mail/chatter/web_portal/chatter";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { onWillStart, useEffect } from "@odoo/owl";

const SELECTORS = {
    hide_send_mail: ".o-mail-Chatter-sendMessage",
    hide_log_notes: ".o-mail-Chatter-logNote",
    hide_schedule_activity: ".o-mail-Chatter-activity",
};

patch(Chatter.prototype, {
    setup() {
        super.setup();
        this.armOrm = useService("orm");
        this.armFlags = {};
        onWillStart(async () => {
            if (!this.props.threadModel) {
                return;
            }
            try {
                this.armFlags = await this.armOrm.call(
                    "access.rights.profile",
                    "get_chatter_flags",
                    [this.props.threadModel]
                );
            } catch {
                this.armFlags = {};
            }
        });
        useEffect(() => {
            const root = this.rootRef && this.rootRef.el;
            if (!root) {
                return;
            }
            for (const [flag, selector] of Object.entries(SELECTORS)) {
                if (this.armFlags[flag]) {
                    root.querySelectorAll(selector).forEach((el) =>
                        el.style.setProperty("display", "none", "important")
                    );
                }
            }
        });
    },
});
