/** @odoo-module **/

import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { Component, onWillStart, useState } from "@odoo/owl";
import { armRootClass } from "../common/theme";

/* Chart geometry constants (viewBox units) */
const LINE_W = 640;
const LINE_H = 200;
const LINE_PAD = { top: 14, right: 14, bottom: 26, left: 34 };

export class AccessRightsDashboard extends Component {
    static template = "access_rights_management.Dashboard";
    static props = ["*"];

    get rootClass() {
        return armRootClass("o_arm_dashboard");
    }

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({
            data: null,
            openRisk: false,
            hoverDay: -1,
            tooltip: null, // {x, y, lines: []}
        });
        onWillStart(() => this.loadData());
    }

    async loadData() {
        this.state.data = await this.orm.call(
            "access.rights.studio", "get_dashboard_data", []);
    }

    async refresh() {
        this.state.data = null;
        this.state.hoverDay = -1;
        this.state.tooltip = null;
        await this.loadData();
    }

    // ================= KPI band =================
    get kpis() {
        const k = this.state.data.kpis;
        return [
            { icon: "fa-shield", tone: "primary", value: k.roles,
              label: _t("Access Profiles"), onClick: () => this.openProfiles() },
            { icon: "fa-sitemap", tone: "info", value: k.departments,
              label: _t("Departments"), onClick: () => this.openDepartments() },
            { icon: "fa-users", tone: "success", value: `${k.covered_users} / ${k.internal_users}`,
              label: _t("Covered Users"), onClick: () => this.openUsers() },
            { icon: "fa-list-ol", tone: "secondary", value: k.rules,
              label: _t("Active Rules"), onClick: () => this.openProfiles() },
            { icon: "fa-laptop", tone: "info", value: k.devices,
              sub: k.blocked_devices ? _t("%s blocked", k.blocked_devices) : "",
              label: _t("Login Devices"), onClick: () => this.openDevices() },
            { icon: "fa-user-secret", tone: "warning", value: k.sensitive_fields,
              label: _t("Sensitive Fields"), onClick: () => this.openSensitive() },
            { icon: "fa-exclamation-triangle",
              tone: k.unusual_logins ? "danger" : "secondary",
              value: k.unusual_logins,
              label: _t("Unusual Logins"), onClick: () => this.openAnomalies() },
            { icon: "fa-ban", tone: "danger", value: k.blocked_logins_7d,
              label: _t("Denied Logins (7d)"), onClick: () => this.openLoginAudit() },
        ];
    }

    // ================= Login activity chart =================
    get lineChart() {
        const series = this.state.data.login_series || [];
        const innerW = LINE_W - LINE_PAD.left - LINE_PAD.right;
        const innerH = LINE_H - LINE_PAD.top - LINE_PAD.bottom;
        const maxVal = Math.max(1, ...series.map((d) => Math.max(d.success, d.denied)));
        // nice max: round up to a multiple of a clean step
        const step = maxVal <= 5 ? 1 : maxVal <= 20 ? 5 : maxVal <= 50 ? 10 : 25;
        const top = Math.ceil(maxVal / step) * step;
        const n = series.length;
        const x = (i) => LINE_PAD.left + (n <= 1 ? innerW / 2 : (i * innerW) / (n - 1));
        const y = (v) => LINE_PAD.top + innerH - (v / top) * innerH;

        const points = series.map((d, i) => ({
            x: x(i), ySuccess: y(d.success), yDenied: y(d.denied), ...d,
        }));
        const path = (key) => points.map(
            (p, i) => `${i === 0 ? "M" : "L"}${p.x.toFixed(1)},${p[key].toFixed(1)}`).join(" ");
        const area = points.length
            ? `${path("ySuccess")} L${points[n - 1].x.toFixed(1)},${(LINE_PAD.top + innerH).toFixed(1)}` +
              ` L${points[0].x.toFixed(1)},${(LINE_PAD.top + innerH).toFixed(1)} Z`
            : "";
        const gridYs = [];
        for (let v = 0; v <= top; v += step) {
            gridYs.push({ y: y(v), value: v });
        }
        // thin the x labels to ~5
        const every = Math.max(1, Math.round(n / 5));
        const xLabels = points.filter((_, i) => i % every === 0 || i === n - 1);
        return { points, successPath: path("ySuccess"), deniedPath: path("yDenied"),
                 area, gridYs, xLabels, baseline: LINE_PAD.top + innerH };
    }

    onLineMove(ev) {
        const svg = ev.currentTarget;
        const rect = svg.getBoundingClientRect();
        const px = ((ev.clientX - rect.left) / rect.width) * LINE_W;
        const chart = this.lineChart;
        if (!chart.points.length) return;
        let best = 0;
        let bestDist = Infinity;
        chart.points.forEach((p, i) => {
            const dist = Math.abs(p.x - px);
            if (dist < bestDist) { bestDist = dist; best = i; }
        });
        this.state.hoverDay = best;
        const p = chart.points[best];
        this.state.tooltip = {
            x: ev.clientX - rect.left,
            y: ev.clientY - rect.top,
            lines: [
                { label: p.date, cls: "head" },
                { label: _t("Successful"), value: p.success, dot: "activity" },
                { label: _t("Denied"), value: p.denied, dot: "denied" },
            ],
        };
    }

    onLineLeave() {
        this.state.hoverDay = -1;
        this.state.tooltip = null;
    }

    // ================= Denied reasons bars =================
    get deniedBars() {
        const reasons = this.state.data.denied_reasons || [];
        const max = Math.max(1, ...reasons.map((r) => r.count));
        return reasons.map((r) => ({ ...r, pct: (r.count / max) * 100 }));
    }

    // ================= Coverage donut =================
    get donut() {
        const c = this.state.data.coverage;
        const total = Math.max(c.covered + c.uncovered, 1);
        const pct = Math.round((c.covered / total) * 100);
        const R = 52;
        const CIRC = 2 * Math.PI * R;
        const covered = (c.covered / total) * CIRC;
        return {
            r: R, circ: CIRC, pct,
            covered: c.covered, uncovered: c.uncovered,
            coveredDash: `${Math.max(covered - 2, 0)} ${CIRC - Math.max(covered - 2, 0)}`,
            uncoveredDash: `${Math.max(CIRC - covered - 2, 0)} ${covered + 2}`,
            uncoveredOffset: -(covered + 2),
        };
    }

    // ================= Hygiene =================
    get hygieneRisks() {
        const h = this.state.data?.hygiene;
        if (!h) return [];
        return [
            { key: "stale", icon: "fa-hourglass-half", tone: h.stale.length ? "warning" : "ok",
              count: h.stale.length, users: h.stale,
              label: _t("Inactive 90+ days"),
              hint: _t("Active accounts that haven't logged in for over 90 days — candidates to archive.") },
            { key: "never", icon: "fa-user-o", tone: h.never_logged_in.length ? "warning" : "ok",
              count: h.never_logged_in.length, users: h.never_logged_in,
              label: _t("Never logged in"),
              hint: _t("Accounts created over 30 days ago that were never used.") },
            { key: "no_profile",
              icon: "fa-unlock",
              tone: h.no_profile.length > 20 ? "danger"
                  : h.no_profile.length ? "warning" : "ok",
              count: h.no_profile.length, users: h.no_profile,
              label: _t("No access profile"),
              hint: _t("Internal users not covered by any access profile — click Roll Out Profiles to cover them by department."),
              action: { label: _t("Roll out"), run: () => this.openRollout() } },
            { key: "admin_grants", icon: "fa-key",
              tone: h.admin_grants_30d ? "danger" : "ok",
              count: h.admin_grants_30d, users: [],
              label: _t("Admin rights granted (30d)"),
              hint: _t("Full-administrator rights handed out in the last 30 days."),
              onClick: () => this.openChanges("admin") },
            { key: "twofa", icon: "fa-mobile", tone: h.twofa_missing.length ? "danger" : "ok",
              count: h.twofa_missing.length, users: h.twofa_missing,
              label: _t("2FA required, not set"),
              hint: _t("Users required to enable two-factor authentication who still haven't.") },
            { key: "admins", icon: "fa-star-o", tone: h.admin_count > 3 ? "danger" : "ok",
              count: h.admin_count, users: h.admins,
              label: _t("Administrators"),
              hint: _t("Full system administrators. Keep this number small.") },
            { key: "blocked_devices", icon: "fa-laptop", tone: h.blocked_devices ? "warning" : "ok",
              count: h.blocked_devices, users: [],
              label: _t("Blocked devices"),
              hint: _t("Devices that are currently denied login."),
              onClick: () => this.openDevices("blocked") },
            { key: "exports", icon: "fa-download", tone: h.large_sensitive_exports_7d ? "danger" : "ok",
              count: h.large_sensitive_exports_7d, users: [],
              label: _t("Large sensitive exports (7d)"),
              hint: _t("Large exports of sensitive data in the last 7 days."),
              onClick: () => this.openExportAudit() },
        ];
    }

    get riskCount() {
        return this.hygieneRisks.filter((r) => r.tone !== "ok" && r.count > 0).length;
    }

    toggleRisk(key) {
        this.state.openRisk = this.state.openRisk === key ? false : key;
    }

    deniedTone(log) {
        return log.status_key === "failed" ? "warning"
            : log.status_key === "kicked" ? "dark" : "danger";
    }

    // ================= Navigation =================
    openProfiles(profileId = false, deptId = false) {
        if (profileId) {
            this.action.doAction({
                type: "ir.actions.act_window",
                res_model: "access.rights.profile",
                res_id: profileId,
                views: [[false, "form"]],
            });
            return;
        }
        this.action.doAction("access_rights_management.action_access_rights_profile", {
            additionalContext: deptId ? { search_default_department_id: deptId } : {},
        });
    }

    newRole(deptId = false) {
        this.action.doAction({
            type: "ir.actions.act_window",
            name: _t("New Access Profile"),
            res_model: "access.rights.profile",
            views: [[false, "form"]],
            context: deptId ? { default_department_id: deptId } : {},
        });
    }

    openDepartments() {
        this.action.doAction("access_rights_management.action_arm_departments");
    }

    openDepartment(dept) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.department",
            res_id: dept.id,
            views: [[false, "form"]],
        });
    }

    openUsers() {
        this.action.doAction("access_rights_management.action_arm_users");
    }

    openUserForm(userId) {
        this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "res.users",
            res_id: userId,
            views: [[false, "form"]],
        });
    }

    openDevices(filter = false) {
        this.action.doAction("access_rights_management.action_arm_devices", {
            additionalContext: filter === "blocked" ? { search_default_blocked: 1 } : {},
        });
    }

    openSensitive() {
        this.action.doAction("access_rights_management.action_arm_sensitive_fields");
    }

    openLoginAudit() {
        this.action.doAction("access_rights_management.action_access_rights_login_log");
    }

    openAnomalies() {
        this.action.doAction("access_rights_management.action_arm_anomalies");
    }

    openChanges(filter = false) {
        this.action.doAction("access_rights_management.action_arm_changes", {
            additionalContext: filter === "admin" ? { search_default_admin: 1 } : {},
        });
    }

    async openRollout() {
        await this.action.doAction(
            "access_rights_management.action_access_rights_rollout_wizard",
            { onClose: () => this.refresh() });
    }

    openExportAudit() {
        this.action.doAction("access_rights_management.action_access_rights_export_log");
    }
}

registry.category("actions").add("access_rights_dashboard", AccessRightsDashboard);
