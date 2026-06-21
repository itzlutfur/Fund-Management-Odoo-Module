{
    'name': "NN Fund Management",
    'version': '1.0',
    'category': 'Accounting',
    'depends': [
        'base',
        'web',
        'account',
        'project',
    ],
    'author': "Lutfur Rahman Tanvir",
    'description': """
    Comprehensive fund management system for managing:
    - Incoming funds and fund accounts
    - Project and expense-head allocations
    - Fund requisitions with approval workflow
    - Bills against approved requisitions
    - Fund transfers between projects/expense heads
    - GM and MD approval workflows
    - Balance tracking (available, held, assigned, spent)
    - Complete audit history and approval trail
    """,
    # data files always loaded at installation
    'data': [
        # Views
        'views/fund_account_view.xml',
        'views/incoming_fund_view.xml',
        'views/expense_head_view.xml',
        'views/fund_balance_view.xml',
        'views/fund_allocation_view.xml',
        'views/fund_requisition_view.xml',
        'views/fund_bill_view.xml',
        'views/fund_transfer_view.xml',
        'views/approval_history_view.xml',
        'views/fund_approver_config_view.xml',
        'views/menus.xml',
    ],
    
    'installable': True,
    'auto_install': False,
    'application': True,
    'maintainer': 'Lutfur Rahman Tanvir',
}