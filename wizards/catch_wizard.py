from odoo import models, fields, api
from odoo.exceptions import UserError
from random import randint, choice

class PokemonCatchWizard(models.TransientModel):
    _name = 'pokedex.catch.wizard'
    _description = 'Catch Pokemon Wizard'
    
    trainer_id = fields.Many2one('res.partner', string='Trainer', 
                                required=True, default=lambda self: self.env.user.partner_id)
    pokemon_id = fields.Many2one('pokedex.pokemon', string='Wild Pokemon Appeared!', readonly=True)
    
    # HACK: Store the Pokemon ID as a regular field that will persist
    target_pokemon_id = fields.Integer(string='Target Pokemon ID')
    
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
        res = super().default_get(fields_list)
        
        trainer = self.env.user.partner_id
        owned_pokemon_ids = trainer.trainer_pokemon_ids.mapped('pokemon_id.id')
        available_pokemon = self.env['pokedex.pokemon'].search([
            ('id', 'not in', owned_pokemon_ids)
        ])
        
        if not available_pokemon:
            raise UserError("Congratulations! You've caught all available Pokemon!")
        
        random_pokemon = choice(available_pokemon)
        res['pokemon_id'] = random_pokemon.id
        res['target_pokemon_id'] = random_pokemon.id  # Store the ID
        res['result_message'] = f"A wild {random_pokemon.name} appeared!"
        
        return res
    
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
        
        if self.has_attempted:
            return {'type': 'ir.actions.do_nothing'}
        
        # HACK: Use the stored target_pokemon_id instead of pokemon_id
        pokemon_id = self.target_pokemon_id
        if not pokemon_id:
            raise UserError("No Pokemon targeted!")
        
        pokemon = self.env['pokedex.pokemon'].browse(pokemon_id)
        if not pokemon.exists():
            raise UserError("Target Pokemon not found!")
        
        pokemon_name = pokemon.name
        
        # Get catch rate for the target Pokemon
        # We need to recalculate since the form might have a different Pokemon
        total_stats = sum([
            pokemon.base_hp,
            pokemon.base_attack,
            pokemon.base_defense,
            pokemon.base_speed
        ])
        is_legendary = total_stats > 500
        stats_penalty = total_stats // 10
        legendary_penalty = 40 if is_legendary else 0
        catch_rate = max(5, 90 - stats_penalty - legendary_penalty)
        
        # Mark as attempted
        self.has_attempted = True
        
        # Roll for catch
        catch_roll = randint(1, 100)
        
        if catch_roll <= catch_rate:
            # Success!
            self.env['pokedex.trainer.pokemon'].create({
                'trainer_id': self.trainer_id.id,
                'pokemon_id': pokemon_id,
                'level': randint(3, 10),
                'experience': 0
            })
            
            message = f"Success! You caught {pokemon_name}!"
            if is_legendary:
                message = f"INCREDIBLE! You caught the legendary {pokemon_name}!"
            
            self.write({
                'catch_success': True,
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
    
    def find_new_pokemon(self):
        """Close the wizard and open a new one with a different Pokemon"""
        # Simply close this wizard and let user open a new one
        return {'type': 'ir.actions.act_window_close'}