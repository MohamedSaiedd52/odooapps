/** @odoo-module **/
import { CogMenu } from "@web/search/cog_menu/cog_menu";
import { patch } from "@web/core/utils/patch";
import { registry } from "@web/core/registry";

const cogMenuRegistry = registry.category("cogMenu");

patch(CogMenu.prototype, {
    setup() {
        super.setup();
        this.armHideSpreadsheet = false;
        const config = this.env.config || {};
        if (config.actionType === "ir.actions.act_window" && config.actionId) {
            this.orm
                .call("access.rights.profile", "is_spreadsheet_hidden", [
                    config.actionType,
                    config.actionId,
                ])
                .then(async (hidden) => {
                    if (hidden) {
                        this.armHideSpreadsheet = true;
                        this.registryItems = await this._registryItems();
                        this.render();
                    }
                })
                .catch(() => {});
        }
    },
    async _registryItems() {
        const items = await super._registryItems();
        if (!this.armHideSpreadsheet) {
            return items;
        }
        return items.filter(
            (item) => !/spreadsheet/i.test(item.Component ? item.Component.name : "")
        );
    },
});
