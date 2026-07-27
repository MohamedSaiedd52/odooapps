/** @odoo-module **/

import { cookie } from "@web/core/browser/cookie";

/** Whether Odoo's dark mode is active (color_scheme cookie). */
export function armIsDark() {
    return cookie.get("color_scheme") === "dark";
}

/** Root classes shared by every Access Rights OWL screen. */
export function armRootClass(screenClass) {
    return `o_arm_app ${screenClass} h-100 overflow-auto` + (armIsDark() ? " o_arm_dark" : "");
}
