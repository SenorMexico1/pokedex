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
    
    # DIAGNOSTIC: Store the initial Pokemon ID to detect changes
    initial_pokemon_id = fields.Integer(string='Initial Pokemon ID', readonly=True)
    
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
    def default_get(self, fields_list):
        """Set initial Pokemon when wizard opens"""
        _logger.warning("CATCH WIZARD: default_get called")
        res = super().default_get(fields_list)
        
        # Get trainer
        trainer = self.env.user.partner_id
        owned_pokemon_ids = trainer.trainer_pokemon_ids.mapped('pokemon_id.id')
        available_pokemon = self.env['pokedex.pokemon'].search([
            ('id', 'not in', owned_pokemon_ids)
        ])
        
        if not available_pokemon:
            raise UserError("Congratulations! You've caught all available Pokemon!")
        
        random_pokemon = choice(available_pokemon)
        res['pokemon_id'] = random_pokemon.id
        res['initial_pokemon_id'] = random_pokemon.id  # Store for comparison
        res['result_message'] = f"A wild {random_pokemon.name} appeared!"
        
        _logger.warning(f"CATCH WIZARD: Selected Pokemon {random_pokemon.name} (ID: {random_pokemon.id})")
        
        return res
    
    @api.model
    def create(self, vals):
        """Log when wizard is created"""
        _logger.warning(f"CATCH WIZARD: create() called with vals: {vals}")
        result = super().create(vals)
        _logger.warning(f"CATCH WIZARD: After create - Pokemon: {result.pokemon_id.name} (ID: {result.pokemon_id.id})")
        return result
    
    def write(self, vals):
        """Log any writes to detect changes"""
        _logger.warning(f"CATCH WIZARD: write() called with vals: {vals}")
        _logger.warning(f"CATCH WIZARD: Before write - Pokemon: {self.pokemon_id.name} (ID: {self.pokemon_id.id})")
        result = super().write(vals)
        _logger.warning(f"CATCH WIZARD: After write - Pokemon: {self.pokemon_id.name} (ID: {self.pokemon_id.id})")
        return result
    
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
        
        _logger.warning(f"CATCH WIZARD: attempt_catch() called")
        _logger.warning(f"CATCH WIZARD: Current Pokemon: {self.pokemon_id.name} (ID: {self.pokemon_id.id})")
        _logger.warning(f"CATCH WIZARD: Initial Pokemon ID was: {self.initial_pokemon_id}")
        
        if self.pokemon_id.id != self.initial_pokemon_id:
            _logger.error(f"CATCH WIZARD: POKEMON CHANGED! Was {self.initial_pokemon_id}, now {self.pokemon_id.id}")
        
        if self.has_attempted:
            return {'type': 'ir.actions.do_nothing'}
        
        # Get Pokemon data
        pokemon_id = self.pokemon_id.id
        pokemon_name = self.pokemon_id.name
        is_legendary = self.is_legendary
        catch_rate = self.catch_rate
        
        _logger.warning(f"CATCH WIZARD: About to roll catch for {pokemon_name} (ID: {pokemon_id})")
        
        # Roll for catch
        catch_roll = randint(1, 100)
        
        if catch_roll <= catch_rate:
            # Success!
            new_pokemon = self.env['pokedex.trainer.pokemon'].create({
                'trainer_id': self.trainer_id.id,
                'pokemon_id': pokemon_id,
                'level': randint(3, 10),
                'experience': 0
            })
            
            _logger.warning(f"CATCH WIZARD: Created trainer Pokemon for {new_pokemon.pokemon_id.name} (ID: {new_pokemon.pokemon_id.id})")
            
            message = f"Success! You caught {pokemon_name}!"
            if is_legendary:
                message = f"INCREDIBLE! You caught the legendary {pokemon_name}!"
            
            self.write({
                'catch_success': True,
                'has_attempted': True,
                'result_message': message
            })
            
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
            
            self.write({
                'catch_success': False,
                'has_attempted': True,
                'result_message': message
            })
            
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