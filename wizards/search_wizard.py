from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PokemonSearchWizard(models.TransientModel):
    _name = 'pokedex.search.wizard'
    _description = 'Search and Import Pokemon from PokeAPI'
    
    # Search field
    search_term = fields.Char(string='Pokemon Name or ID',
                             help="Enter a Pokemon name (e.g., 'pikachu') or ID (e.g., '25')")
    
    # Result fields
    found_pokemon_id = fields.Many2one('pokedex.pokemon', string='Found Pokemon', readonly=True)
    search_message = fields.Text(string='Status', readonly=True)  # Changed to Text
    
    # Progress tracking fields
    import_progress = fields.Float(string='Progress', default=0.0)
    import_log = fields.Text(string='Import Log', default='')
    is_importing = fields.Boolean(string='Import in Progress', default=False)
    
    def search_pokemon(self):
        """Search for a Pokemon in the database or import from API"""
        self.ensure_one()
        
        if not self.search_term:
            raise UserError("Please enter a Pokemon name or ID to search!")
        
        existing_pokemon = self.env['pokedex.pokemon'].search([
            '|', 
            ('name', 'ilike', self.search_term),
            ('pokedex_number', '=', int(self.search_term) if self.search_term.isdigit() else -1)
        ], limit=1)
        
        if existing_pokemon:
            self.found_pokemon_id = existing_pokemon
            self.search_message = f"Found {existing_pokemon.name} in the Pokedex!"
            
            return {
                'type': 'ir.actions.act_window',
                'res_model': 'pokedex.pokemon',
                'res_id': existing_pokemon.id,
                'view_mode': 'form',
                'target': 'current',
            }
        else:
            self.search_message = f"Pokemon '{self.search_term}' not found in database. You can import it from the API."
            
            return self.refresh_wizard()
    
    def import_batch(self):
        """Import ALL Pokemon from the PokeAPI with detailed error logging"""
        self.ensure_one()
        
        try:
            api_sync = self.env['pokedex.api.sync']
            
            existing_ids = self.env['pokedex.pokemon'].search([]).mapped('pokedex_number')

            MAX_POKEMON_ID = 1010
            all_ids = set(range(1, MAX_POKEMON_ID + 1))
            missing_ids = sorted(all_ids - set(existing_ids))
            
            if not missing_ids:
                self.write({
                    'search_message': 'All Pokemon are already imported!',
                    'import_log': f'Database already contains all {len(existing_ids)} Pokemon.',
                    'import_progress': 100.0
                })
                return self.refresh_wizard()
            
            self.write({
                'is_importing': True,
                'import_progress': 0.0,
                'search_message': f'Starting import of {len(missing_ids)} Pokemon...',
                'import_log': f'=== POKEMON IMPORT LOG ===\nImporting {len(missing_ids)} Pokemon\n\n'
            })
            self.env.cr.commit()
            
            imported = 0
            failed = 0
            consecutive_failures = 0
            
            for i, pokemon_id in enumerate(missing_ids):
                try:
                    self.import_log += f"\nAttempting Pokemon #{pokemon_id}... "
                    self.env.cr.commit()  # Save immediately
                    
                    pokemon = api_sync.import_pokemon(pokemon_id)
                    
                    imported += 1
                    consecutive_failures = 0
                    self.import_log += f"✓ SUCCESS - {pokemon.name}\n"
                    
                    progress = ((i + 1) / len(missing_ids)) * 100
                    self.search_message = f'Progress: {progress:.1f}% - Imported {imported}/{i + 1} attempted'
                    self.import_progress = progress
                    
                    self.env.cr.commit()
                    
                except Exception as e:
                    failed += 1
                    consecutive_failures += 1
                    
                    error_type = type(e).__name__
                    error_msg = str(e)
                    
                    self.import_log += f"FAILED\n"
                    self.import_log += f"Error Type: {error_type}\n"
                    self.import_log += f"Error Message: {error_msg}\n"
                    
                    _logger.error(f"Pokemon #{pokemon_id} failed: {error_type}: {error_msg}")
                    
                    if hasattr(e, 'args') and e.args:
                        self.import_log += f"  Details: {e.args}\n"
                    
                    self.search_message = f'Progress: Some imports failing - Last error: {error_msg[:50]}...'
                    
                    self.env.cr.commit()
                    
                    if consecutive_failures >= 10:
                        self.import_log += f"\nStopped after {consecutive_failures} consecutive failures\n"
                        break
            
            # Final summary
            self.import_log += f"\n\n=== IMPORT COMPLETE ===\n"
            self.import_log += f"Successfully imported: {imported}\n"
            self.import_log += f"Failed: {failed}\n"
            self.import_log += f"Total Pokemon in database: {self.env['pokedex.pokemon'].search_count([])}\n"
            
            if failed > 0:
                self.import_log += f"\nCheck the errors above to see why imports failed.\n"
                self.import_log += f"Common issues:\n"
                self.import_log += f"- Network/firewall blocking PokeAPI\n"
                self.import_log += f"- Missing 'requests' library (pip install requests)\n"
                self.import_log += f"- API rate limiting (try adding delays)\n"
            
            self.write({
                'is_importing': False,
                'import_progress': 100.0,
                'search_message': f'Import Complete! Imported: {imported}, Failed: {failed}'
            })
            
            return self.refresh_wizard()
            
        except Exception as e:
            import traceback
            error_trace = traceback.format_exc()
            
            self.write({
                'is_importing': False,
                'search_message': f'Import crashed: {str(e)}',
                'import_log': self.import_log + f'\n\nERROR:\n{error_trace}'
            })
            
            _logger.error(f"Import batch crashed: {error_trace}")
            raise UserError(f"Import failed: {str(e)}")
    
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