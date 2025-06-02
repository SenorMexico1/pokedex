from odoo import models, fields, api
from odoo.exceptions import UserError

class PokemonSearchWizard(models.TransientModel):
    _name = 'pokedex.search.wizard'
    _description = 'Search and Import Pokemon from PokeAPI'
    
    # Search field
    search_term = fields.Char(string='Pokemon Name or ID', required=True,
                             help="Enter a Pokemon name (e.g., 'pikachu') or ID (e.g., '25')")
    
    # Result fields
    found_pokemon_id = fields.Many2one('pokedex.pokemon', string='Found Pokemon', readonly=True)
    search_message = fields.Char(string='Search Result', readonly=True)

    def search_pokemon(self):
        """Search for a Pokemon in the database or import from API"""
        self.ensure_one()
        
        if not self.search_term:
            raise UserError("Please enter a Pokemon name or ID to search!")
        
        # First, try to find the Pokemon in our database
        existing_pokemon = self.env['pokedex.pokemon'].search([
            '|', 
            ('name', 'ilike', self.search_term),
            ('pokedex_number', '=', int(self.search_term) if self.search_term.isdigit() else -1)
        ], limit=1)
        
        if existing_pokemon:
            # Pokemon already exists in database
            self.found_pokemon_id = existing_pokemon
            self.search_message = f"Found {existing_pokemon.name} in the Pokedex!"
            
            # Open the Pokemon form view
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pokedex.pokemon',
                'res_id': existing_pokemon.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            # Pokemon not in database, ask if they want to import it
            self.search_message = f"Pokemon '{self.search_term}' not found in database."
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pokedex.search.wizard',
                'res_id': self.id,
                'view_mode': 'form',
                'target': 'new',
                'context': {'show_import_option': True}
            }