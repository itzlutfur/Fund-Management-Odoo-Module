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
        
    ],
    
    'installable': True,
    'auto_install': False,
    'application': True,
    'maintainer': 'Lutfur Rahman Tanvir',
}