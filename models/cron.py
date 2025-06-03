# Update your models/cron.py file with this simplified version:

from odoo import models, fields, api
from random import randint

class PokemonExperienceCron(models.Model):
    _name = 'pokedex.experience.cron'
    _description = 'Pokemon Experience Cron'
    
    # Award between 1-10 XP randomly
    @api.model
    def _award_experience(self):
        """Cron job to award experience to all trainer pokemon"""
        trainer_pokemons = self.env['pokedex.trainer.pokemon'].search([])
        
        for pokemon in trainer_pokemons:
            xp_gain = randint(1, 10)
            pokemon.experience += xp_gain
            