# -*- coding: utf-8 -*-
{
    'name': 'FS HR Shifts & Attendance Sheets',
    'version': '17.0.1.0.0',
    'category': 'Human Resources',
    'summary': """All-in-one HR shifts management: attendance sheets & policies,
        multi-shift planning integration, automatic shift generation and
        planning by department / tags.""",
    'description': """
        Merged module combining:
        - rm_hr_attendance_sheet : Attendance sheets, policies (overtime /
          late-in / absence / difference-time rules), sheet batches and
          payslip integration.
        - fs_multi_shifts        : Multi-shift contracts. Work entries and
          attendance sheets computed from Planning slots instead of the
          fixed working calendar.
        - planning_shifts_generator : Wizard to bulk-generate planning
          shifts per role with special Thursday hours, Friday off and a
          second period, plus contract auto-switch to planning source.
        - fs_planning            : Create planning slots for a whole
          department or employee tags at once.
    """,
    'author': 'Mohamed Saied',
    'depends': [
        'hr',
        'hr_attendance',
        'hr_holidays',
        'hr_payroll',
        'hr_work_entry_contract',
        'planning',
    ],
    'data': [
        'data/ir_sequence.xml',
        'data/data.xml',
        'security/security.xml',
        'security/ir.model.access.csv',
        'wizard/change_att_data_view.xml',
        'views/hr_attendance_sheet_view.xml',
        'views/hr_attendance_policy_view.xml',
        'views/hr_contract_view.xml',
        'views/attendance_sheet_batch_view.xml',
        'views/hr_payslip_view.xml',
        'views/planning_views.xml',
        'views/generate_shifts_views.xml',
    ],
    'images': ['static/description/banner.gif'],
    'license': 'OPL-1',
    'installable': True,
    'application': True,
    'price': 90.0,
    'currency': 'USD',
}
