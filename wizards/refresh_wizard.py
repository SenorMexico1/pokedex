# In your search_wizard.py, change this:

def refresh_wizard(self):
    """Return action to refresh the wizard and show updated data"""
    return {
        'type': 'ir.actions.act_window',
        'res_model': 'pokedex.search.wizard',
        'res_id': self.id,
        'view_mode': 'form',
        'target': 'new',
        'context': dict(self.env.context)
    }