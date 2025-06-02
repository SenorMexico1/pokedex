from odoo import models, fields, api
from odoo.exceptions import UserError
from random import randint, choice
import logging

_logger = logging.getLogger(__name__)

class PokemonCatchWizard(models.TransientModel):
    _name = 'pokedex.catch.wizard'
    _description = 'Catch Pokemon Wizard'
    
    trainer_id = fields.Many2one('res.partner', string='Trainer', 
                                required=True, default=lambda self: self.env.user.partner_id)
    pokemon_id = fields.Many2one('pokedex.pokemon', string='Wild Pokemon Appeared!', readonly=True)
    
    # Display fields
    pokemon_image = fields.Char(related='pokemon_id.image_url', string='Pokemon Image')
    pokemon_type = fields.Many2one(related='pokemon_id.type_id', string='Type')
    pokemon_stats_display = fields.Text(string='Pokemon Stats', compute='_compute_pokemon_stats_display')
    
    # Catch info
    catch_rate = fields.Integer(string='Catch Rate %', compute='_compute_catch_rate')
    is_legendary = fields.Boolean(string='Legendary Pokemon', compute='_compute_is_legendary')
    
    # Result tracking
    catch_success = fields.Boolean(string='Catch Success', readonly=True, default=False)
    result_message = fields.Char(string='Result', readonly=True)
    has_attempted = fields.Boolean(string='Has Attempted', default=False)
    
    @api.model
    def create(self, vals):
        """Override create to set Pokemon if not provided"""
        record = super().create(vals)
        if not record.pokemon_id:
            # Get a random available Pokemon
            trainer = record.trainer_id
            owned_pokemon_ids = trainer.trainer_pokemon_ids.mapped('pokemon_id.id')
            available_pokemon = self.env['pokedex.pokemon'].search([
                ('id', 'not in', owned_pokemon_ids)
            ])
            
            if not available_pokemon:
                raise UserError("Congratulations! You've caught all available Pokemon!")
            
            random_pokemon = choice(available_pokemon)
            record.pokemon_id = random_pokemon
            record.result_message = f"A wild {random_pokemon.name} appeared!"
        
        return record
    
    @api.depends('pokemon_id')
    def _compute_pokemon_stats_display(self):
        for wizard in self:
            if wizard.pokemon_id:
                wizard.pokemon_stats_display = (
                    f"HP: {wizard.pokemon_id.base_hp}\n"
                    f"Attack: {wizard.pokemon_id.base_attack}\n"
                    f"Defense: {wizard.pokemon_id.base_defense}\n"
                    f"Speed: {wizard.pokemon_id.base_speed}"
                )
            else:
                wizard.pokemon_stats_display = ""
    
    @api.depends('pokemon_id')
    def _compute_is_legendary(self):
        for wizard in self:
            if wizard.pokemon_id:
                total_stats = sum([
                    wizard.pokemon_id.base_hp,
                    wizard.pokemon_id.base_attack,
                    wizard.pokemon_id.base_defense,
                    wizard.pokemon_id.base_speed
                ])
                wizard.is_legendary = total_stats > 500
            else:
                wizard.is_legendary = False
    
    @api.depends('pokemon_id', 'is_legendary')
    def _compute_catch_rate(self):
        for wizard in self:
            if wizard.pokemon_id:
                base_rate = 90
                total_stats = sum([
                    wizard.pokemon_id.base_hp,
                    wizard.pokemon_id.base_attack,
                    wizard.pokemon_id.base_defense,
                    wizard.pokemon_id.base_speed
                ])
                stats_penalty = total_stats // 10
                legendary_penalty = 40 if wizard.is_legendary else 0
                wizard.catch_rate = max(5, base_rate - stats_penalty - legendary_penalty)
            else:
                wizard.catch_rate = 0
    
    def attempt_catch(self):
        """Attempt to catch the Pokemon"""
        self.ensure_one()
        
        # Double-click protection
        if self.has_attempted:
            return {'type': 'ir.actions.do_nothing'}
        
        # Get all data BEFORE any database operations
        pokemon_id = self.pokemon_id.id
        pokemon_name = self.pokemon_id.name
        is_legendary = self.is_legendary
        catch_rate = self.catch_rate
        trainer_id = self.trainer_id.id
        
        # Roll for catch
        catch_roll = randint(1, 100)
        
        if catch_roll <= catch_rate:
            # Success!
            self.env['pokedex.trainer.pokemon'].create({
                'trainer_id': trainer_id,
                'pokemon_id': pokemon_id,
                'level': randint(3, 10),
                'experience': 0
            })
            
            message = f"Success! You caught {pokemon_name}!"
            if is_legendary:
                message = f"INCREDIBLE! You caught the legendary {pokemon_name}!"
            
            # Update wizard state
            self.sudo().write({
                'catch_success': True,
                'has_attempted': True,
                'result_message': message
            })
            
            # Force commit to ensure state is saved
            self.env.cr.commit()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pokemon Caught!',
                    'message': message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # Failed
            message = f"Oh no! {pokemon_name} escaped!"
            if catch_roll <= catch_rate + 10:
                message = f"So close! {pokemon_name} broke free at the last second!"
            
            # Update wizard state
            self.sudo().write({
                'catch_success': False,
                'has_attempted': True,
                'result_message': message
            })
            
            # Force commit
            self.env.cr.commit()
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pokemon Escaped!',
                    'message': message,
                    'type': 'warning',
                    'sticky': False,
                }
            }
    
    def find_new_pokemon(self):
        """Create a completely new wizard to ensure fresh state"""
        self.ensure_one()
        
        # Get available Pokemon for the new wizard
        trainer = self.trainer_id
        owned_pokemon_ids = trainer.trainer_pokemon_ids.mapped('pokemon_id.id')
        
        # Exclude current Pokemon if it wasn't caught
        exclude_ids = owned_pokemon_ids.copy()
        if not self.catch_success and self.pokemon_id:
            exclude_ids.append(self.pokemon_id.id)
        
        available_pokemon = self.env['pokedex.pokemon'].search([
            ('id', 'not in', exclude_ids)
        ])
        
        if not available_pokemon:
            raise UserError("No other Pokemon available right now!")
        
        # Select a random Pokemon for the new wizard
        random_pokemon = choice(available_pokemon)
        
        # Create a brand new wizard with the new Pokemon
        new_wizard = self.create({
            'trainer_id': trainer.id,
            'pokemon_id': random_pokemon.id,
            'result_message': f"A wild {random_pokemon.name} appeared!",
            'has_attempted': False,
            'catch_success': False
        })
        
        # Delete the current wizard to avoid confusion
        current_id = self.id
        
        # Return action to open the new wizard
        action = {
            'type': 'ir.actions.act_window',
            'res_model': 'pokedex.catch.wizard',
            'res_id': new_wizard.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }
        
        # Delete current wizard after preparing the action
        self.browse(current_id).unlink()
        
        return action