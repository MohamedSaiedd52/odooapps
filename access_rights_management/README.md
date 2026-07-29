# Access Rights Management (Odoo 19)

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

---

# Migration 18.0 → 19.0

Everything that had to change to move this module from Odoo 18 to Odoo 19, in
roughly the order it bites. These changes are **not** backwards compatible — the
18.0 tree stays on 18.0.

Module version: `18.0.2.3.1` → `19.0.2.4.0`.

## 0. Run the official rewriter first

Odoo 19 ships mechanical migration scripts. They do the boring third of the job:

```bash
python -m odoo upgrade_code --from 18.1 \
       --addons-path /path/to/custom_addon \
       --glob "access_rights_management/**/*"
```

What it rewrote here:

| Change | Where |
|---|---|
| `@http.route(type='json')` → `type='jsonrpc'` | `controllers/main.py` (3 routes) |
| `_sql_constraints = [(...)]` → `_field_uniq = models.Constraint(...)` | `models/security_audit.py` |
| Dynamic date domains in search filters → the new relative syntax (`'today'`, `'today -7d'`) | `views/access_profile_views.xml`, `anomaly_views.xml`, `login_log_views.xml`, `security_views.xml` |

It rewrites files with CRLF endings — normalise afterwards if that matters to
you. It is a best-effort helper; everything below it did **not** catch.

## 1. Groups: `groups_id` is gone, and implied groups are no longer stored

The biggest change. Odoo 19 renamed the group relations **and** changed their
meaning:

| 18.0 | 19.0 | Meaning |
|---|---|---|
| `res.users.groups_id` | `res.users.group_ids` | **explicitly** assigned groups |
| — | `res.users.all_group_ids` | explicit **+ implied** (computed) |
| `res.groups.users` | `res.groups.user_ids` | explicit members |
| — | `res.groups.all_user_ids` | explicit + implied members |
| `ir.actions.act_window.groups_id` | `group_ids` | same on `ir.actions.server`, `ir.ui.menu`, `ir.ui.view` |

The trap: 18.0 *materialised* implied groups into `groups_id`, so
`admin_group in user.groups_id` also matched a user who only held an implying
group. In 19.0 `group_ids` holds explicit memberships only. **A blind rename to
`group_ids` silently breaks every "is this user an admin?" test.** Anything that
means *effective* membership must use `all_group_ids` / `all_user_ids`.

| File | Change |
|---|---|
| `models/res_users.py` | `write()` change tracking: `'groups_id' in vals` → `'group_ids' in vals`, snapshot `user.group_ids` |
| `wizard/copy_access_wizard.py` | copying a user's groups → `group_ids` (explicit membership is what you want to copy) |
| `models/access_studio.py` | admin detection → `u.all_group_ids` |
| `wizard/rollout_wizard.py` | "skip administrators" → `user.all_group_ids` |
| `models/login_anomaly.py`, `models/security_audit.py` | manager lookup `search([('groups_id','in',…)])` → `('all_group_ids','in',…)` |
| `models/security_audit.py` | "who can read this field" → `group_id.all_user_ids`, `field.groups.mapped('all_user_ids')` |
| `views/copy_access_wizard_views.xml`, `views/rollout_wizard_views.xml` | `<field name="groups_id">` on `ir.actions.act_window` → `group_ids` |

## 2. Domains are objects, not lists

`odoo.osv.expression` still exists in 19.0 but is deprecated, and
**`ir.rule._compute_domain()` now returns a `Domain`** instead of a
list of tuples. `models/ir_rule.py` was rewritten:

| 18.0 | 19.0 |
|---|---|
| `from odoo.osv import expression` | `from odoo.fields import Domain` |
| `expression.normalize_domain(d)` | `Domain(d)` |
| `expression.TRUE_DOMAIN` / `FALSE_DOMAIN` | `Domain.TRUE` / `Domain.FALSE` |
| `expression.OR([...])` / `AND([...])` | `Domain.OR([...])` / `Domain.AND([...])`, or `a & b` |
| `expression.AND([res or [], extra])` | `(res if res is not None else Domain.TRUE) & extra` |

Watch the truthiness: `bool(Domain)` is `True` when the domain **has
conditions**, so a trivially-true domain is falsy. `res or []` no longer means
what it used to — test explicitly.

## 3. `res.users._login` is no longer a classmethod

| 18.0 | 19.0 |
|---|---|
| `@classmethod def _login(cls, db, credential, user_agent_env)` | `def _login(self, credential, user_agent_env)` |
| `cls.pool.cursor()` | `self.pool.cursor()` |
| `db` argument | `self.env.cr.dbname` |

In `models/res_users.py` both `_login` and the `_arm_log_login` helper became
regular methods, and the `super()` call lost its `db` argument.

## 4. `Session` lost its generic attribute proxy

18.0 let you hang any key on the session as an attribute. 19.0's `Session` has
`__slots__` plus explicit properties for the known keys only (`uid`, `db`,
`login`, `context`, `debug`, `session_token`).

```python
# 18.0
request.session.pre_login = user.login
request.session.pre_uid = user.id
# 19.0
request.session['pre_login'] = user.login
request.session['pre_uid'] = user.id
```

Affects the "simulate a user" flow in `models/access_studio.py`.
`session.debug`, `session.uid`, `session.get()`, `session.pop()` and
`session.logout(keep_db=True)` are unchanged.

## 5. Groups are filed under a privilege, not a module category

`res.groups.category_id` no longer exists. A group points at a
`res.groups.privilege`, and *that* carries the `ir.module.category`
(`security/security.xml`):

```xml
<record id="privilege_access_rights" model="res.groups.privilege">
    <field name="name">Access Rights Management</field>
    <field name="category_id" ref="module_category_access_rights"/>
</record>

<record id="group_access_rights_manager" model="res.groups">
    <field name="privilege_id" ref="privilege_access_rights"/>   <!-- was category_id -->
</record>
```

`implied_ids` is unchanged.

## 6. Search views: `<group>` no longer takes `expand`

The 19.0 RNG rejects `expand` (and `string`) on a `<group>` inside `<search>`.
The symptom is a hard install failure —
`RELAXNG_ERR_INVALIDATTR: Invalid attribute expand for element group`, followed
by misleading knock-on errors about `search has extra content: field`.

```xml
<!-- 18.0 -->  <group expand="0" string="Group By">
<!-- 19.0 -->  <group name="group_by">
```

7 occurrences across `access_profile_views.xml`, `anomaly_views.xml`,
`login_log_views.xml`, `security_views.xml`.

## 7. JS — the pivot header is gone

`@web/views/pivot/pivot_header` no longer exists; 19.0 folded the group-by field
list into `PivotRenderer`. `static/src/js/pivot_header_patch.js` was renamed to
`pivot_patch.js` and now patches:

```js
import { PivotRenderer } from "@web/views/pivot/pivot_renderer";
patch(PivotRenderer.prototype, { setup() { /* … */ } });
```

It still has to sit in **`web.assets_backend_lazy`** (see the manifest): pivot
and graph are served on demand, so a file importing from them out of
`web.assets_backend` never loads at all — and silently takes its own module down
with it for the whole session.

## 8. JS — the export flow moved into a hook

This one has no drop-in equivalent. 18.0 owned the export request in
`ListController.downloadExport` / `onExportData` / `onDirectExportData`, so the
audit block (`arm_origin`: screen, action, view type, saved template) was added
by overriding those methods.

19.0 moved the whole flow into `useExportRecords()` in `@web/views/view_hook`,
where the download call is a **closure** — nothing is left on the controller to
patch.

`static/src/js/export_audit_patch.js` was rewritten to work one level lower:

* **`download._download`** is intercepted. Core exposes it as an assignable
  property precisely so it can be swapped, and *both* export paths (the
  "Export…" dialog and "Export All") funnel through it. The interceptor parses
  `options.data.data`, injects `arm_origin`, and re-serialises.
* The context it injects is recorded by the components that actually know it:
  `ListController` / `KanbanController` (`setup` → current screen),
  `ExportAll.onDirectExportData` (screen, no template) and
  `ExportDataDialog.onClickExportButton` (chosen template).

Bonus: the 18.0 version had to inject a custom `armSetTemplate` prop into
`ExportDataDialog`; 19.0 needs no prop injection at all.

### `patch()` gotcha found while doing this

`patch()` rewires the *extension object's* prototype so `super` resolves, which
means **the same object literal must never be handed to two prototypes** — the
second call re-points it, and `super.setup()` from the first target then lands in
the wrong class. Symptom: `Cannot destructure property 'rawExpand' of
'this.archInfo' as it is undefined` on every list view. Use a factory:

```js
function armRememberScreen() {
    return { setup() { super.setup(...arguments); /* … */ } };
}
patch(ListController.prototype, armRememberScreen());
patch(KanbanController.prototype, armRememberScreen());
```

## 9. Callers of `ir.autovacuum._run_vacuum_cleaner`

19.0 requires `cron_id` in the context, else `AccessDenied`:

```python
env['ir.autovacuum'].with_context(cron_id=1)._run_vacuum_cleaner()
```

The module's own `@api.autovacuum` methods (`_gc_login_logs`, `_gc_export_logs`,
`_gc_anomalies`) are unchanged — this only affects scripts and tests that trigger
the vacuum by hand.

## Verified unchanged (checked, no edit needed)

Useful to know what you do *not* have to touch:

* **View pipeline** — `_get_view_cache_key`, `_get_view`, `get_views`, the
  `_postprocess_tag_{tag}` dispatcher and the `_postprocess_tag_field` /
  `_postprocess_tag_label` signatures, the `<chatter/>` tag.
* **Security hooks** — `ir.model.access.check` / `_make_access_error`,
  `ir.ui.menu._visible_menu_ids` / `load_menus`, `ir.http._auth_method_user`,
  `ir.http.session_info`.
* **Controllers** — `Action.load` / `run`, `Export.get_fields`, `CSVExport`,
  `ExcelExport`, `Home.web_client` and `Home._web_client_readonly`.
* **Session/request** — `finalize()`, `logout()`, `request.update_env()`,
  `request.redirect_query()`, `future_response.set_cookie(cookie_type=…)`.
* **ORM helpers** — `tools.ormcache`, `@api.autovacuum`, `@api.depends_context`,
  `@api.model_create_multi`, `_compute_display_name`,
  `env.registry.clear_all_caches()`, `mail.thread.message_notify`, `_tz_get`,
  `ir.model.fields.groups`.
* **JS** — `Chatter` (same path and props), `ActionMenus.getActionItems`,
  `CogMenu._registryItems`, `SearchBarMenu.fields`,
  `ModelFieldSelectorPopover.loadPages`, `FormController.actionMenuItems`,
  `ExportDataDialog` internals, `@web/core/browser/cookie`,
  `web.assets_backend_lazy`.

## How this was verified

On a real Odoo 19 server, not by reading diffs:

| Check | Result |
|---|---|
| Clean install on an empty database | pass |
| Endpoint probe — dashboard, `get_views` for every model, every action, the RPC endpoints the JS patches call | 30/30 |
| Enforcement with a real restricted user — fields, chatter, buttons, record rules, ACL, read-only, simulate | 17/17 |
| View types, nodes, search, toolbar, login policy, session kick, export audit, wizards, cron, autovacuum | 28/28 |
| Headless Chrome — every screen, no console error | 14/14 |
| Headless Chrome in debug mode (OWL props validation on) — cog menu, export dialog, pivot lazy bundle, all profile tabs, dashboard | 14/14 |
