from odoo import models, fields, api
from odoo.exceptions import UserError
from random import randint, choice
from datetime import datetime, timedelta

class PokemonCatchWizard(models.TransientModel):
    _name = 'pokedex.catch.wizard'
    _description = 'Catch Pokemon Wizard'
    
    trainer_id = fields.Many2one('res.partner', string='Trainer', 
                                required=True, default=lambda self: self.env.user.partner_id)
    pokemon_id = fields.Many2one('pokedex.pokemon', string='Wild Pokemon Appeared!', readonly=True)
    
    target_pokemon_id = fields.Integer(string='Target Pokemon ID')
    
    pokemon_image = fields.Char(related='pokemon_id.image_url', string='Pokemon Image')
    pokemon_type = fields.Many2one(related='pokemon_id.type_id', string='Type')
    pokemon_stats_display = fields.Text(string='Pokemon Stats', compute='_compute_pokemon_stats_display')
    
    catch_rate = fields.Integer(string='Catch Rate %', compute='_compute_catch_rate')
    is_legendary = fields.Boolean(string='Legendary Pokemon', compute='_compute_is_legendary')
    
    catch_success = fields.Boolean(string='Catch Success', readonly=True, default=False)
    result_message = fields.Char(string='Result', readonly=True)
    has_attempted = fields.Boolean(string='Has Attempted', default=False)
    image_html = fields.Html(string='Image', compute='_compute_image_html', sanitize=False)

    cooldown_message = fields.Char(string='Cooldown Message', readonly=True)
    can_catch = fields.Boolean(string='Can Catch', default=True)
    
    @api.model
    def default_get(self, fields_list):
        """Set initial Pokemon when wizard opens"""
        res = super().default_get(fields_list)
        
        trainer = self.env.user.partner_id
        
        if not trainer.is_trainer:
            trainer.is_trainer = True
        
        if trainer.last_catch_attempt:
            time_since_last = datetime.now() - trainer.last_catch_attempt
            cooldown_remaining = timedelta(minutes=15) - time_since_last
            
            if cooldown_remaining.total_seconds() > 0:
                minutes = int(cooldown_remaining.total_seconds() // 60)
                seconds = int(cooldown_remaining.total_seconds() % 60)
                res['cooldown_message'] = f"Please wait {minutes}m {seconds}s before catching another Pokemon!"
                res['can_catch'] = False
                res['result_message'] = "You need to wait before catching another Pokemon."
                return res
        
        owned_pokemon_ids = trainer.trainer_pokemon_ids.mapped('pokemon_id.id')
        available_pokemon = self.env['pokedex.pokemon'].search([
            ('id', 'not in', owned_pokemon_ids)
        ])
        
        if not available_pokemon:
            raise UserError("Congratulations! You've caught all available Pokemon!")
        
        random_pokemon = choice(available_pokemon)
        res['pokemon_id'] = random_pokemon.id
        res['target_pokemon_id'] = random_pokemon.id
        res['result_message'] = f"A wild {random_pokemon.name} appeared!"
        res['can_catch'] = True
        
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
                legendary_ids = [
                    144, 145, 146, 150, 151,
                    243, 244, 245, 249, 250, 251,
                    377, 378, 379, 380, 381, 382, 383, 384, 385, 386,
                    480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493,
                    494, 638, 639, 640, 641, 642, 643, 644, 645, 646, 647, 648, 649,
                    716, 717, 718, 719, 720, 721,
                    772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 793, 794, 795, 796, 
                    797, 798, 799, 800, 801, 802, 803, 804, 805, 806, 807, 808, 809,
                    888, 889, 890, 891, 892, 893, 894, 895, 896, 897, 898,
                    905, 1001, 1002, 1003, 1004, 1007, 1008, 1009, 1010, 1014, 1015, 1016, 
                    1017, 1020, 1021, 1022, 1023, 1024, 1025,
                ]
                wizard.is_legendary = wizard.pokemon_id.pokedex_number in legendary_ids
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
        
        if not self.can_catch:
            return {'type': 'ir.actions.do_nothing'}
        
        if self.has_attempted:
            return {'type': 'ir.actions.do_nothing'}
        
        self.trainer_id.last_catch_attempt = datetime.now()
        pokemon_id = self.target_pokemon_id
        if not pokemon_id:
            raise UserError("No Pokemon targeted!")
        
        pokemon = self.env['pokedex.pokemon'].browse(pokemon_id)
        if not pokemon.exists():
            raise UserError("Target Pokemon not found!")
        
        pokemon_name = pokemon.name
        
        total_stats = sum([
            pokemon.base_hp,
            pokemon.base_attack,
            pokemon.base_defense,
            pokemon.base_speed
        ])
        legendary_ids = [
            144, 145, 146, 150, 151,
            243, 244, 245, 249, 250, 251,
            377, 378, 379, 380, 381, 382, 383, 384, 385, 386,
            480, 481, 482, 483, 484, 485, 486, 487, 488, 489, 490, 491, 492, 493,
            494, 638, 639, 640, 641, 642, 643, 644, 645, 646, 647, 648, 649,
            716, 717, 718, 719, 720, 721,
            772, 773, 785, 786, 787, 788, 789, 790, 791, 792, 793, 794, 795, 796, 
            797, 798, 799, 800, 801, 802, 803, 804, 805, 806, 807, 808, 809,
            888, 889, 890, 891, 892, 893, 894, 895, 896, 897, 898,
            905, 1001, 1002, 1003, 1004, 1007, 1008, 1009, 1010, 1014, 1015, 1016, 
            1017, 1020, 1021, 1022, 1023, 1024, 1025,
        ]
        is_legendary = pokemon.pokedex_number in legendary_ids
        stats_penalty = total_stats // 10
        legendary_penalty = 40 if is_legendary else 0
        catch_rate = max(5, 90 - stats_penalty - legendary_penalty)

        self.has_attempted = True 
        catch_roll = randint(1, 100)
        
        if catch_roll <= catch_rate:
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
                    'next': {'type': 'ir.actions.act_window_close'}
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
                    'next': {'type': 'ir.actions.act_window_close'}
                }
            }
    
    def find_new_pokemon(self):
        """Close the wizard and open a new one with a different Pokemon"""
        return {'type': 'ir.actions.act_window_close'}

    @api.depends('pokemon_image')
    def _compute_image_html(self):
        for wizard in self:
            if wizard.pokemon_image:
                wizard.image_html = '<img src="%s" style="max-width: 300px; max-height: 300px; border-radius: 10px;" />' % wizard.pokemon_image
            else:
                wizard.image_html = '<p>No image</p>'