# Access Rights Management (Odoo 17)

Central access-rights management, rebuilt from scratch as a clean replacement for
`simplify_access_management` / `sh_access_management`-style apps.

## What it does

Create **Access Profiles** (menu *Access Rights*) and assign users. Each profile can:

| Tab | Effect |
|---|---|
| Menus | Hide menus/sub-menus |
| Models | Hide create/edit/delete/duplicate/archive/import/export buttons, view types, reports, server actions, spreadsheet (UI level) |
| Fields | Invisible / read-only / required / remove external link — invisible fields are also stripped from export, filters, group-by and field selectors |
| Records | **Strict** ORM-level read/create/update/delete rules with optional domain filter (applies to UI *and* API). Rules can only restrict, never widen base security |
| Buttons & Tabs | Hide buttons, smart buttons, notebook tabs, kanban links (auto-scanned from views) |
| Search | Hide predefined filters and group-by options |
| Chatter | Hide chatter or its buttons per model |
| Global | Chatter/import/export/spreadsheet/properties switches for all models |

Profile-level switches: **Read-Only User** (system-wide), **Disable Developer Mode**, **Disable Login**.
Multi-company aware: apply everywhere or only in selected companies.
Profiles are chatter-tracked (who changed what, when).

## v1.7.0 — Business/security features

| Feature | Details |
|---|---|
| **Validity period** | `Valid From / Until` per profile — temporary access (auditor, vacation cover). Evaluated in UTC; a daily cron (00:05 UTC) refreshes the caches and chatter-logs started/expired profiles. |
| **Live session enforcement** | Disable Login / IP / hours are enforced on *every request* (`ir.http._auth_method_user`): an open session is terminated on the next request, not at the next login. |
| **Allowed IPs** | Per profile, comma-separated IPs or CIDR networks. Works because `proxy_mode = True` (real client IP behind nginx). |
| **Login hours** | Per profile: allowed weekdays + hour window in a chosen timezone. |
| **Login Audit** | `access.rights.login.log` — success / wrong credentials / blocked (disabled, IP, hours) / terminated sessions, with IP + user agent. Auto-vacuumed after 180 days (`access_rights_management.login_log_retention_days`, 0 disables). |
| **Copy User Access** | Wizard: copy groups and/or profiles from one user to others, add or replace. Also in the Action menu of any user. |
| **User Access Matrix (Excel)** | Reporting menu: users overview, user × group matrix, profiles, and every profile rule — for audits/access reviews. |

Safety: **system administrators are always exempt** from IP/hours/disable-login
enforcement, so a bad rule can never lock the admins out. Failed enforcement
paths fail open (never brick login or request dispatch) and are logged.

## v1.8.0 — Studio screens become fully manageable

| Feature | Details |
|---|---|
| **Users: inline profiles** | Assign / remove access profiles directly on the user card (picker), plus a per-user **copy** shortcut that opens the Copy User Access wizard pre-filled with that user as source. |
| **Groups: inline members** | Click a group card to expand its member list — add / remove internal users without leaving the screen (native `res.groups` security still applies). The pencil icon opens the raw group form. |
| **Profile History tab** | The chatter audit trail (tracked field changes + notes) is now visible inside the OWL editor: who changed what, old → new, and when. |
| **Record-rule domain tester** | A flask button next to each domain filter validates the domain server-side (same eval context as `ir.rule`) and reports the number of matching records — before the rule ever hits a user. |
| **Dashboard: denied logins feed** | The last denied / failed / kicked logins are listed on the dashboard with reason, IP and time; the Covered Users KPI now opens the OWL Users screen. |

## v1.9.0 — Inspector, portability, Arabic

| Feature | Details |
|---|---|
| **Effective Access Inspector** | *Inspect* button on every user card: one panel showing exactly which profiles hit that user (direct vs global, companies, validity) and every restriction they carry — menus, models, fields, record rules, buttons, search, chatter, login security. Answers "why can't this user see X?" without opening each profile. |
| **Profile Export / Import (JSON)** | *Export* downloads a profile as portable JSON (all references by name). *Import* (profiles list) pastes a JSON export — from this or another database — resolving models/fields/menus/nodes by name; anything missing is skipped and reported as warnings + logged in the profile chatter. Made for moving profiles from For_Test to production. |
| **Arabic translation** | `i18n/ar.po` — 526 terms covering every OWL screen, menus, fields, wizards, error messages and help texts. Loads automatically on module upgrade for `ar_*` languages. |

## v1.10.0 — Security operations layer

| Feature | Details |
|---|---|
| **Live Sessions** | *Security → Live Sessions*: everyone currently connected (from the presence signal) with status, last activity and last-login IP. **Terminate** queues a one-shot forced logout enforced on the target's next request (`ir.http`), for a fired employee or a lost device — recorded in the Login Audit. Auto-refreshes every 20 s. |
| **Security Hygiene** | Dashboard panel of ready-to-act risks: users inactive 90+ days, never-logged-in accounts, users with no profile, admin count (red above 3), 2FA-required-but-missing, and large sensitive exports (7 d). Each risk expands to the user list; click a user to open them. |
| **Sensitive Data Map** | *Security → Sensitive Data*: flag business-sensitive fields (salary, cost, purchase price, credit limit...) and see exactly which users can read each one **right now** — via their groups' ACL, any field-level group restriction, minus what ARM profiles already hide. |
| **Require 2FA (per profile)** | Login-Security switch. Non-compliant users are surfaced in Security Hygiene and stamped `2FA Missing` in the Login Audit at login. Soft by design (a hard block would deadlock — users could not reach preferences to enable it); admins exempt. |
| **Export Audit** | Every CSV/Excel export is logged (who, model, record & field count, format, IP). Exports of a sensitive model or a flagged field are marked; a **large sensitive export** also notifies the managers via `message_notify`. Tunable with `access_rights_management.sensitive_models` and `access_rights_management.export_alert_threshold` (default 100). Auto-vacuumed after 180 days. |

## Login audit without MAC, export audit with context

| Feature | Details |
|---|---|
| **MAC address removed** | A MAC never crosses a router, so the column was empty for every client that is not on the server's own subnet — and it was the key devices were matched on. Removed from `access.rights.login.log`, `access.rights.device` and `access.rights.anomaly`, together with the ARP/ping lookup. |
| **Device identity that works** | A device is identified by a random `arm_device_id` cookie issued at login (2 years, HttpOnly, SameSite=Lax, `cookie_type='required'`), so it survives IP changes. Clients with no cookie (RPC, curl) fall back to a User-Agent fingerprint + IP. Clearing the cookie does not lift a block: the same browser on the same address is still matched by fingerprint. Devices can now be named (`label`). |
| **Migration** | The post-migrate script backfills `fingerprint` from the stored user agent (so a **blocked device stays blocked**), merges the rows that only differed by MAC, and drops the three columns. |
| **Export Audit: which fields** | `line_ids` (`access.rights.export.log.line`) — one record per exported column with its header, technical path, type and sensitivity, in the user's own order. Plus `field_labels` and `sensitive_fields` on the log itself. |
| **Export Audit: which screen** | `screen_name`, `action_id`, `view_type`, `scope` (selected records vs. the whole filter). |
| **Export Audit: which template** | `export_template_id` / `template_name` — the saved `ir.exports` template that built the field list, or empty when the fields were picked by hand; `import_compat` records the re-importable format. |
| **How it is captured** | `static/src/js/export_audit_patch.js` adds an `arm_origin` block to the `/web/export/*` payload (screen from `env.config`, template from the export dialog). The server validates every reference before storing it, and a failure there never breaks the download. New form view + search/group-by on screen, template and column name. |
| **Documentation** | `static/description/index.html` — bilingual (EN/AR) guide with an illustration and a numbered legend for every screen. |

## Why it is better than simplify_access_management

1. **No global cache flushes on page loads.** The old app cleared *all* registry caches
   on every `/web` request (because Odoo caches rendered views across users). This module
   instead gives profiled users their own view-cache key (`_get_view_cache_key`), so
   unaffected users keep full caching. Caches are flushed only when a profile changes.
2. **All rule lookups are `ormcache`d** — view postprocessing does dict lookups instead of
   SQL per field/button/tab node.
3. **Record rules are enforced by the ORM** (`ir.rule._compute_domain` + `ir.model.access.check`)
   instead of a per-record Python `search()` inside `base.write`/`base.unlink` (a big write
   slowdown in the old app). Restrictions AND with existing rules — they can never widen access.
4. **No paid dependency**: uses the native `domain` widget instead of `advanced_web_domain_widget`.
5. **No mirror models** (`menu.item`, `action.data`) — direct `many2many` to `ir.ui.menu`,
   `ir.actions.report`, `ir.actions.server`.
6. No string-concatenated SQL, no bare `except:`; guards for install/uninstall states.
7. Safety: admins can't be made read-only, the app's own models/menu can't be restricted,
   modern OWL patches (no jQuery `setInterval` hacks for chatter).

## Install

```bash
sudo systemctl stop odoo   # or use a staging DB first
/opt/odoo/odoo-venv/bin/python3 /opt/odoo/odoo/odoo-bin -c /etc/odoo/odoo.conf -d live_live -i access_rights_management --stop-after-init
sudo systemctl start odoo
```

Managers group: *Access Rights Management / Manager* (auto-granted to Settings admins).

## Notes

- Read-only users keep write access to a small whitelist (`res.users`, presence, activities…)
  so the web client still works — see `READONLY_SAFE_MODELS`.
- "Records" rules replace the group ACL check for that model when present; everything else
  is UI-level hiding (like the original apps).
- Button/tab lists fill automatically when you pick a model in *Buttons & Tabs* / *Search*
  (views are scanned once per model).
