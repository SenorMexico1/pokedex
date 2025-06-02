from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PokemonSearchWizard(models.TransientModel):
    _name = 'pokedex.search.wizard'
    _description = 'Search and Import Pokemon from PokeAPI'
    
    # Search field - NOT REQUIRED
    search_term = fields.Char(string='Pokemon Name or ID',
                             help="Enter a Pokemon name (e.g., 'pikachu') or ID (e.g., '25')")
    
    # Result fields
    found_pokemon_id = fields.Many2one('pokedex.pokemon', string='Found Pokemon', readonly=True)
    search_message = fields.Text(string='Status', readonly=True)  # Changed to Text
    
    # NEW Progress tracking fields
    import_progress = fields.Float(string='Progress', default=0.0)
    import_log = fields.Text(string='Import Log', default='')
    is_importing = fields.Boolean(string='Import in Progress', default=False)
    
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
            # Pokemon not in database
            self.search_message = f"Pokemon '{self.search_term}' not found in database. You can import it from the API."
            
            return self.refresh_wizard()
    
    def import_batch(self):
        """Import ALL Pokemon from the PokeAPI with detailed progress tracking"""
        self.ensure_one()
        
        try:
            api_sync = self.env['pokedex.api.sync']
            
            # Get existing Pokemon IDs
            existing_ids = self.env['pokedex.pokemon'].search([]).mapped('pokedex_number')
            
            # Determine range
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
            
            # Initialize import
            self.write({
                'is_importing': True,
                'import_progress': 0.0,
                'search_message': f'Starting import of {len(missing_ids)} missing Pokemon...',
                'import_log': f'=== POKEMON IMPORT LOG ===\nFound {len(missing_ids)} Pokemon to import\n\n'
            })
            
            # Commit to show initial state
            self.env.cr.commit()
            
            # Import Pokemon with detailed progress
            imported = 0
            failed = 0
            log_entries = []
            
            for i, pokemon_id in enumerate(missing_ids):
                try:
                    # Import the Pokemon
                    pokemon = api_sync.import_pokemon(pokemon_id)
                    imported += 1
                    
                    log_entry = f"✓ #{pokemon_id} - {pokemon.name}"
                    log_entries.append(log_entry)
                    
                    # Update progress every 5 Pokemon
                    if (i + 1) % 5 == 0 or (i + 1) == len(missing_ids):
                        progress = ((i + 1) / len(missing_ids)) * 100
                        
                        # Keep only last 20 log entries for display
                        recent_logs = '\n'.join(log_entries[-20:])
                        if len(log_entries) > 20:
                            recent_logs = f"... (showing last 20 of {len(log_entries)} entries)\n" + recent_logs
                        
                        self.write({
                            'import_progress': progress,
                            'search_message': f'Progress: {progress:.1f}% - Imported {imported}/{len(missing_ids)} Pokemon',
                            'import_log': self.import_log + recent_logs + '\n'
                        })
                        
                        # Commit to save progress
                        self.env.cr.commit()
                        
                except Exception as e:
                    failed += 1
                    log_entry = f"✗ #{pokemon_id} - Error: {str(e)}"
                    log_entries.append(log_entry)
                    _logger.warning(f"Failed to import Pokemon #{pokemon_id}: {str(e)}")
            
            # Final update
            final_count = self.env['pokedex.pokemon'].search_count([])
            final_message = f"\n\n=== IMPORT COMPLETE ===\n" \
                          f"Successfully imported: {imported}\n" \
                          f"Failed: {failed}\n" \
                          f"Total Pokemon in database: {final_count}"
            
            self.write({
                'is_importing': False,
                'import_progress': 100.0,
                'search_message': f'Import Complete! Imported: {imported}, Failed: {failed}',
                'import_log': self.import_log + final_message
            })
            
            return self.refresh_wizard()
            
        except Exception as e:
            self.write({
                'is_importing': False,
                'search_message': f'Import failed with error: {str(e)}',
                'import_log': self.import_log + f'\n\n❌ FATAL ERROR: {str(e)}'
            })
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