from odoo import models, fields, api
from odoo.exceptions import UserError
import logging

_logger = logging.getLogger(__name__)

class PokemonImportWizard(models.TransientModel):
    _name = 'pokedex.import.wizard'
    _description = 'Import Pokemon from PokeAPI'
    
    # Import options
    import_option = fields.Selection([
        ('gen1', 'Generation 1 (Kanto: 1-151)'),
        ('gen2', 'Generation 2 (Johto: 152-251)'),
        ('gen3', 'Generation 3 (Hoenn: 252-386)'),
        ('gen4', 'Generation 4 (Sinnoh: 387-493)'),
        ('gen5', 'Generation 5 (Unova: 494-649)'),
        ('gen6', 'Generation 6 (Kalos: 650-721)'),
        ('gen7', 'Generation 7 (Alola: 722-809)'),
        ('gen8', 'Generation 8 (Galar: 810-898)'),
        ('all', 'All Pokemon (1-898)'),
        ('missing', 'Only Missing Pokemon'),
        ('custom', 'Custom Range')
    ], string='Import Option', required=True, default='missing')
    
    # Custom range fields
    start_id = fields.Integer(string='Start ID', default=1)
    end_id = fields.Integer(string='End ID', default=151)
    
    # Status fields
    total_pokemon = fields.Integer(string='Total Pokemon in Database', 
                                  compute='_compute_stats', store=False)
    missing_count = fields.Integer(string='Missing Pokemon Count', 
                                  compute='_compute_stats', store=False)
    import_message = fields.Text(string='Import Status', readonly=True)
    
    @api.depends('import_option')
    def _compute_stats(self):
        for wizard in self:
            total = self.env['pokedex.pokemon'].search_count([])
            wizard.total_pokemon = total
            
            # Calculate missing Pokemon (assuming max 898 for Gen 8)
            existing_ids = self.env['pokedex.pokemon'].search([]).mapped('pokedex_number')
            missing_ids = set(range(1, 899)) - set(existing_ids)
            wizard.missing_count = len(missing_ids)
    
    @api.onchange('import_option')
    def _onchange_import_option(self):
        """Set the ID range based on selected generation"""
        ranges = {
            'gen1': (1, 151),
            'gen2': (152, 251),
            'gen3': (252, 386),
            'gen4': (387, 493),
            'gen5': (494, 649),
            'gen6': (650, 721),
            'gen7': (722, 809),
            'gen8': (810, 898),
            'all': (1, 898),
        }
        
        if self.import_option in ranges:
            self.start_id, self.end_id = ranges[self.import_option]
        elif self.import_option == 'missing':
            # Set to full range for missing check
            self.start_id, self.end_id = 1, 898
    
    def action_check_missing(self):
        """Check which Pokemon are missing from the database"""
        existing_ids = self.env['pokedex.pokemon'].search([]).mapped('pokedex_number')
        missing_ids = []
        
        for pokemon_id in range(self.start_id, self.end_id + 1):
            if pokemon_id not in existing_ids:
                missing_ids.append(pokemon_id)
        
        if missing_ids:
            self.import_message = (
                f"Missing Pokemon IDs: {', '.join(map(str, missing_ids[:20]))}"
                f"{' and more...' if len(missing_ids) > 20 else ''}\n"
                f"Total missing: {len(missing_ids)} Pokemon"
            )
        else:
            self.import_message = "All Pokemon in this range are already imported!"
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pokedex.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }
    
    def action_import(self):
        """Import Pokemon based on selected option"""
        self.ensure_one()
        
        if self.import_option == 'custom':
            if self.start_id > self.end_id:
                raise UserError("Start ID must be less than or equal to End ID!")
            if self.start_id < 1 or self.end_id > 898:
                raise UserError("Pokemon IDs must be between 1 and 898!")
        
        api_sync = self.env['pokedex.api.sync']
        imported_count = 0
        skipped_count = 0
        failed_count = 0
        
        # Get existing Pokemon IDs for efficiency
        existing_ids = self.env['pokedex.pokemon'].search([]).mapped('pokedex_number')
        
        # Determine which IDs to import
        if self.import_option == 'missing':
            ids_to_import = []
            for pokemon_id in range(self.start_id, self.end_id + 1):
                if pokemon_id not in existing_ids:
                    ids_to_import.append(pokemon_id)
        else:
            ids_to_import = range(self.start_id, self.end_id + 1)
        
        if not ids_to_import:
            self.import_message = "All Pokemon in this range are already imported!"
            return self._return_wizard()
        
        # Show progress notification
        total_to_import = len(ids_to_import)
        self.env['bus.bus'].sendone(
            (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
            {
                'type': 'simple_notification',
                'title': 'Import Started',
                'message': f'Importing {total_to_import} Pokemon... This may take a few minutes.'
            }
        )
        
        # Import Pokemon
        for i, pokemon_id in enumerate(ids_to_import):
            try:
                if pokemon_id in existing_ids and self.import_option != 'missing':
                    skipped_count += 1
                    continue
                
                api_sync.import_pokemon(pokemon_id)
                imported_count += 1
                
                # Send progress update every 10 Pokemon
                if (i + 1) % 10 == 0:
                    progress = ((i + 1) / total_to_import) * 100
                    self.env['bus.bus'].sendone(
                        (self._cr.dbname, 'res.partner', self.env.user.partner_id.id),
                        {
                            'type': 'simple_notification',
                            'title': 'Import Progress',
                            'message': f'Progress: {progress:.0f}% ({i + 1}/{total_to_import})'
                        }
                    )
                
            except Exception as e:
                failed_count += 1
                _logger.error(f"Failed to import Pokemon {pokemon_id}: {str(e)}")
        
        # Set final message
        self.import_message = (
            f"Import completed!\n"
            f"✓ Imported: {imported_count} Pokemon\n"
            f"⚠ Skipped (already exists): {skipped_count} Pokemon\n"
            f"✗ Failed: {failed_count} Pokemon\n"
            f"Total in database: {self.env['pokedex.pokemon'].search_count([])}"
        )
        
        # Show completion notification
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Import Complete!',
                'message': f'Successfully imported {imported_count} Pokemon!',
                'type': 'success',
                'sticky': False,
                'next': self._return_wizard()
            }
        }
    
    def _return_wizard(self):
        """Return action to keep wizard open with updated message"""
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pokedex.import.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }