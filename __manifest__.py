{
    'name': "pokedex_app",
    'description': "Pokedex App with PokéAPI Integration",
    'author': "Andre Romero",
    'category': 'Customizations',
    'version': '0.1',
    'depends': ['base', 'web', 'base_automation'],
    'data': [
        'security/ir.model.access.csv',
        'data/scheduled_xp.xml',
        'views/templates.xml',
        'data/api_actions.xml',
        # Load wizard views FIRST
        'wizards/views/import_wizard_views.xml',
        'wizards/views/catch_wizard_views.xml',
        'wizards/views/search_wizard_views.xml',
        'wizards/views/progress_wizard_views.xml',
        # Then load main views that reference wizard actions
        'views/views.xml',
        'data/pokemon_level_up.xml',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
}