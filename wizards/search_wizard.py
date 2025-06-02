from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

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
            # Add this method to your PokemonSearchWizard class in search_wizard.py

    def import_batch(self):
        """Import ALL Pokemon from the PokeAPI (smart mode - only missing ones)"""
        try:
            api_sync = self.env['pokedex.api.sync']
            
            # Get existing Pokemon IDs
            existing_ids = self.env['pokedex.pokemon'].search([]).mapped('pokedex_number')
            
            # Determine range - PokeAPI currently has data up to #1010
            # Some IDs might be missing (forms/variants), so we'll check up to 1010
            MAX_POKEMON_ID = 1010
            
            # Find missing IDs
            all_ids = set(range(1, MAX_POKEMON_ID + 1))
            missing_ids = sorted(all_ids - set(existing_ids))
            
            if not missing_ids:
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Already Complete!',
                        'message': f'All Pokemon are already imported! Total: {len(existing_ids)}',
                        'type': 'success',
                        'sticky': False,
                    }
                }
            
            # Show what we're about to do
            self.search_message = f"Found {len(missing_ids)} missing Pokemon to import..."
            
            # Show progress notification
            if hasattr(self.env['bus.bus'], 'sendone'):
                self.env['bus.bus'].sendone(
                    (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
                    {'type': 'simple_notification', 
                    'title': 'Smart Import Started',
                    'message': f'Importing {len(missing_ids)} missing Pokemon...'}
                )
            
            # Import only missing Pokemon
            imported = 0
            failed = 0
            
            for i, pokemon_id in enumerate(missing_ids):
                try:
                    api_sync.import_pokemon(pokemon_id)
                    imported += 1
                    
                    # Log progress
                    if (i + 1) % 10 == 0:
                        progress = ((i + 1) / len(missing_ids)) * 100
                        _logger.info(f"Import progress: {progress:.1f}% ({i + 1}/{len(missing_ids)})")
                        
                except Exception as e:
                    failed += 1
                    _logger.warning(f"Failed to import Pokemon #{pokemon_id}: {str(e)}")
                    continue
            
            # Final count
            final_count = self.env['pokedex.pokemon'].search_count([])
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Import Complete!',
                    'message': f'Imported {imported} new Pokemon! Total in database: {final_count}',
                    'type': 'success',
                    'sticky': False,
                }
            }
            
        except Exception as e:
            raise UserError(f"Error during batch import: {str(e)}")