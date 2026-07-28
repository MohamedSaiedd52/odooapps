# -*- coding: utf-8 -*-
{
    'name': 'Access Rights Management',
    'version': '18.0.2.3.1',
    'sequence': 5,
    'author': 'Mohamed Saied',
    'maintainer': 'MS — IT Department',
    'license': 'LGPL-3',
    'price': 60.0,
    'currency': 'USD',
    'category': 'Extra Tools',
    'summary': "One screen to decide who sees what — profiles, record rules, "
               "login security, device control and a full audit trail.",
    'description': """
Access Rights Management
========================

Everything about *who may see and do what* in one app: build **Access
Profiles**, assign them to users or whole departments, and read back — at any
moment — who has access to what, who changed it, and who took data out.

Design the access
-----------------
* **Menus** — hide menus and sub-menus.
* **Models** — hide create / edit / delete / duplicate / archive / import /
  export, hide view types, reports and server actions.
* **Fields** — invisible, read-only, required, or without the external link.
  An invisible field also disappears from exports, filters and group-by.
* **Records** — ORM-level read / write / create / delete rules with a domain.
  Enforced for the API too, and they can only restrict, never widen.
* **Buttons & Tabs** — hide buttons, smart buttons, notebook tabs, kanban links.
* **Search** — hide predefined filters and group-by options.
* **Chatter** — hide the chatter or single chatter buttons, globally or per model.
* **Profile switches** — read-only user, no developer mode, no login at all,
  validity period for temporary access (auditors, holiday cover).

Roll it out
-----------
* **Roll Out Profiles** — start from safe templates (Read-Only Auditor,
  Standard Staff, Sensitive Data) and cover a whole department in one click.
* **Copy User Access** — copy groups and profiles from one user to others.
* **Simulate a user** — see the UI exactly as they see it, no password needed,
  both ends written to the audit trail.

Watch it
--------
* **Dashboard** — coverage, rules, login activity, denied reasons and a
  security-hygiene panel of risks you can act on straight away.
* **Login Audit** — every attempt: success, wrong password, blocked (login
  disabled / IP / hours / device), terminated session, 2FA missing, with the
  device, IP, browser and OS behind it.
* **Login Devices** — every device a user connects from, recognised by a
  long-lived identifier in its browser (not by MAC, which a server behind a
  router can never see). Name them, trust them, block them: a blocked device
  cannot log in even with the right password.
* **Unusual Logins** — new device, new IP, odd hour, burst of failed attempts,
  two networks at once — with a notification to the managers.
* **Permission Changes** — who granted or revoked what, to whom, and when;
  grants of administrator rights are flagged in red.
* **Sensitive Data** — flag the fields that matter (salary, cost, margin) and
  see who can read each one right now.
* **Export Audit** — every CSV/Excel download with **the exact columns**, the
  **screen** it was made from and the **saved template** that built the field
  list. Large exports of sensitive data notify the managers.

Login security
--------------
Allowed IPs/networks, allowed weekdays and hours per timezone, 2FA
requirement, and live enforcement: a policy that changes takes effect on the
user's next request, not at their next login. Administrators are always exempt,
so a bad rule can never lock everyone out.

Built for performance
---------------------
Profiled users get their own view-cache key instead of the global cache
flush-on-every-page-load that similar apps do, and every rule lookup is
ORM-cached.
""",
    'depends': ['web', 'mail', 'auth_totp', 'hr'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'data/view_type_data.xml',
        'data/ir_cron_data.xml',
        'views/access_profile_views.xml',
        'views/departments_views.xml',
        'views/users_groups_views.xml',
        'views/res_users_views.xml',
        'views/login_log_views.xml',
        'views/security_views.xml',
        'views/anomaly_views.xml',
        'views/copy_access_wizard_views.xml',
        'views/rollout_wizard_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            # view patches (menus, buttons, chatter, filters, export origin)
            'access_rights_management/static/src/js/action_menus_patch.js',
            'access_rights_management/static/src/js/chatter_patch.js',
            'access_rights_management/static/src/js/cog_menu_patch.js',
            'access_rights_management/static/src/js/form_controller_patch.js',
            'access_rights_management/static/src/js/field_selector_patch.js',
            'access_rights_management/static/src/js/search_menu_patch.js',
            'access_rights_management/static/src/js/export_audit_patch.js',
            # shared look & feel
            'access_rights_management/static/src/scss/theme.scss',
            'access_rights_management/static/src/common/theme.js',
            # dashboard (the only OWL screen)
            'access_rights_management/static/src/dashboard/dashboard.js',
            'access_rights_management/static/src/dashboard/dashboard.xml',
            'access_rights_management/static/src/dashboard/dashboard.scss',
            # "you are simulating X" banner
            'access_rights_management/static/src/simulate/simulate_banner.js',
            'access_rights_management/static/src/simulate/simulate_banner.xml',
            'access_rights_management/static/src/simulate/simulate_banner.scss',
        ],
        # 18.0 serves the pivot and graph views on demand: a patch importing
        # from them has to sit in the lazy bundle, or it never loads at all.
        'web.assets_backend_lazy': [
            'access_rights_management/static/src/js/pivot_header_patch.js',
        ],
    },
    'images': ['static/description/banner.png'],
    'post_init_hook': 'post_init_hook',
    'application': True,
    'installable': True,
    'auto_install': False,
}
