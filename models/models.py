from odoo import models, fields, api
from random import randint, choice

class PokemonType(models.Model):
    _name = 'pokedex.type'
    _description = 'Pokemon Type'

    name = fields.Char(string='Type Name', required=True)
    color = fields.Char(string='Type Color', help="HTML color code")
    strength_against = fields.Many2many('pokedex.type', 'type_strength_rel', 'type_id', 'strength_id', string='Strong Against')
    weakness_against = fields.Many2many('pokedex.type', 'type_weakness_rel', 'type_id', 'weakness_id', string='Weak Against')
    pokemon_ids = fields.One2many('pokedex.pokemon', 'type_id', string='Pokemon with this Type')
    
class PokemonSkill(models.Model):
    _name = 'pokedex.skill'
    _description = 'Pokemon Skill'
    
    name = fields.Char(string='Skill Name', required=True)
    type_id = fields.Many2one('pokedex.type', string='Skill Type')
    power = fields.Integer(string='Power')
    description = fields.Text(string='Description')
    pokemon_ids = fields.Many2many('pokedex.pokemon', string='Pokemon with this Skill')
    
class Pokemon(models.Model):
    _name = 'pokedex.pokemon'
    _description = 'Pokemon'
    
    name = fields.Char(string='Pokemon Name', required=True)
    pokedex_number = fields.Integer(string='Pokedex Number', required=True)
    type_id = fields.Many2one('pokedex.type', string='Primary Type', required=True)
    secondary_type_id = fields.Many2one('pokedex.type', string='Secondary Type')
    skill_ids = fields.Many2many('pokedex.skill', string='Skills')
    
    base_hp = fields.Integer(string='Base HP', default=100)
    base_attack = fields.Integer(string='Base Attack', default=50)
    base_defense = fields.Integer(string='Base Defense', default=50)
    base_speed = fields.Integer(string='Base Speed', default=50)
    
    height = fields.Float(string='Height (m)', digits=(3, 1))
    weight = fields.Float(string='Weight (kg)', digits=(5, 1))
    image_url = fields.Char(string='Pokemon Image URL')
    description = fields.Text(string='Description')
    
    image_html = fields.Html(string='Image', compute='_compute_image_html', sanitize=False)

    def action_refresh_from_api(self):
        """Refresh Pokemon data from PokeAPI"""
        api_sync = self.env['pokedex.api.sync']
        for pokemon in self:
            api_sync.import_pokemon(pokemon.pokedex_number)
        return True
    
    @api.depends('image_url')
    def _compute_image_html(self):
        for record in self:
            if record.image_url:
                record.image_html = '<img src="%s" style="max-width: 200px; max-height: 200px; border-radius: 10px;" />' % record.image_url
            else:
                record.image_html = '<p>No image</p>'
    
    
class Trainer(models.Model):
    _inherit = 'res.partner'
    _description = 'Pokemon Trainer'
    
    is_trainer = fields.Boolean(string='Is a Trainer', default=False)
    trainer_pokemon_ids = fields.One2many('pokedex.trainer.pokemon', 'trainer_id', string='Caught Pokemon')
    pokemon_count = fields.Integer(string='Pokemon Count', compute='_compute_pokemon_count')
    trainer_level = fields.Integer(string='Trainer Level', default=1)
    partner_gid = fields.Integer(string='Partner GID')
    additional_info = fields.Text(string='Additional Info')
    last_catch_attempt = fields.Datetime(string='Last Catch Attempt')

    @api.depends('trainer_pokemon_ids')
    def _compute_pokemon_count(self):
        for trainer in self:
            trainer.pokemon_count = len(trainer.trainer_pokemon_ids)
    
    def action_open_catch_wizard(self):
        """Open the catch Pokemon wizard"""
        return {
            'name': 'Catch Pokemon',
            'type': 'ir.actions.act_window',
            'res_model': 'pokedex.catch.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_trainer_id': self.id}
        }
            
class TrainerPokemon(models.Model):
    _name = 'pokedex.trainer.pokemon'
    _description = 'Trainer Pokemon'
    
    pokemon_id = fields.Many2one('pokedex.pokemon', string='Pokemon', required=True)
    trainer_id = fields.Many2one('res.partner', string='Trainer', required=True, 
                                domain=[('is_trainer', '=', True)])
    nickname = fields.Char(string='Nickname')
    level = fields.Integer(string='Level', default=1)
    experience = fields.Integer(string='Experience', default=0)
    
    experience_next_level = fields.Integer(string='XP for Next Level', 
                                         compute='_compute_experience_next_level',
                                         store=True)
    experience_progress = fields.Char(string='XP Progress', 
                                    compute='_compute_experience_progress')
    
    hp = fields.Integer(string='HP', compute='_compute_stats', store=True)
    attack = fields.Integer(string='Attack', compute='_compute_stats', store=True)
    defense = fields.Integer(string='Defense', compute='_compute_stats', store=True)
    speed = fields.Integer(string='Speed', compute='_compute_stats', store=True)
    
    image_url = fields.Char(related='pokemon_id.image_url', string='Image URL')
    image_html = fields.Html(string='Image', compute='_compute_image_html', sanitize=False)

    @api.depends('level')
    def _compute_experience_next_level(self):
        """Compute XP needed for next level"""
        for pokemon in self:
            pokemon.experience_next_level = 100 * pokemon.level
    
    @api.depends('experience', 'experience_next_level')
    def _compute_experience_progress(self):
        """Show XP progress as a string"""
        for pokemon in self:
            pokemon.experience_progress = f"{pokemon.experience}/{pokemon.experience_next_level}"
    
    @api.depends('pokemon_id', 'level')
    def _compute_stats(self):
        for pokemon in self:
            if pokemon.pokemon_id:
                pokemon.hp = pokemon.pokemon_id.base_hp + (pokemon.level * 5)
                pokemon.attack = pokemon.pokemon_id.base_attack + (pokemon.level * 2)
                pokemon.defense = pokemon.pokemon_id.base_defense + (pokemon.level * 2)
                pokemon.speed = pokemon.pokemon_id.base_speed + (pokemon.level * 2)
    
    def level_up(self):
        """Level up the Pokemon (kept for backward compatibility)"""
        for pokemon in self:
            pokemon.level += 1
    
    def check_level_up(self):
        """Check if Pokemon should level up based on experience"""
        for pokemon in self:
            if pokemon.experience >= pokemon.experience_next_level:
                overflow_xp = pokemon.experience - pokemon.experience_next_level
                
                pokemon.level += 1
                
                pokemon.experience = overflow_xp
                
                if pokemon.trainer_id.user_ids:
                    message = f"{pokemon.nickname or pokemon.pokemon_id.name} reached level {pokemon.level}!"
                    pokemon.trainer_id.user_ids[0].notify_info(
                        title="Pokemon Level Up!",
                        message=message
                    )
                
                return True
        return False

    @api.depends('image_url')
    def _compute_image_html(self):
        for record in self:
            if record.image_url:
                record.image_html = '<img src="%s" style="max-width: 200px; max-height: 200px; border-radius: 10px;" />' % record.image_url
            else:
                record.image_html = '<p>No image</p>'