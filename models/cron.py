# Update your models/cron.py file with this simplified version:

from odoo import models, fields, api
from random import randint

class PokemonExperienceCron(models.Model):
    _name = 'pokedex.experience.cron'
    _description = 'Pokemon Experience Cron'
    
    @api.model
    def _award_experience(self):
        """Cron job to award experience to all trainer pokemon"""
        trainer_pokemons = self.env['pokedex.trainer.pokemon'].search([])
        
        for pokemon in trainer_pokemons:
            # Award between 1-10 XP randomly
            xp_gain = randint(1, 10)
            
            # Simply update experience - the automated action will handle level-ups
            pokemon.experience += xp_gain
            
        # No level-up logic here anymore - automated action handles it