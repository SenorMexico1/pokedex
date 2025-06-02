from odoo import models, fields, api
from odoo.exceptions import UserError
from random import randint, choice
import logging

_logger = logging.getLogger(__name__)

class PokemonCatchWizard(models.TransientModel):
    _name = 'pokedex.catch.wizard'
    _description = 'Catch Pokemon Wizard'
    
    # The trainer who is trying to catch a Pokemon
    trainer_id = fields.Many2one('res.partner', string='Trainer', 
                                required=True, default=lambda self: self.env.user.partner_id)
    
    # The randomly selected Pokemon to try to catch
    pokemon_id = fields.Many2one('pokedex.pokemon', string='Wild Pokemon Appeared!', readonly=True)
    
    # Display info about the Pokemon
    pokemon_image = fields.Char(related='pokemon_id.image_url', string='Pokemon Image')
    pokemon_type = fields.Many2one(related='pokemon_id.type_id', string='Type')
    pokemon_stats_display = fields.Text(string='Pokemon Stats', compute='_compute_pokemon_stats_display')
    
    # Catch rate info
    catch_rate = fields.Integer(string='Catch Rate %', compute='_compute_catch_rate')
    is_legendary = fields.Boolean(string='Legendary Pokemon', compute='_compute_is_legendary')
    
    # Catch result fields
    catch_success = fields.Boolean(string='Catch Success', readonly=True)
    result_message = fields.Char(string='Result', readonly=True)
    
    # State to track if we've attempted to catch
    has_attempted = fields.Boolean(string='Has Attempted', default=False)
    
    @api.model
    def default_get(self, fields):
        """Override to randomly select a Pokemon when wizard opens"""
        res = super().default_get(fields)
        
        # Get all Pokemon that the trainer doesn't already have
        trainer = self.env.user.partner_id
        owned_pokemon_ids = trainer.trainer_pokemon_ids.mapped('pokemon_id.id')
        
        # Find available Pokemon to catch
        available_pokemon = self.env['pokedex.pokemon'].search([
            ('id', 'not in', owned_pokemon_ids)
        ])
        
        if not available_pokemon:
            raise UserError("Congratulations! You've already caught all available Pokemon!")
        
        # Randomly select one
        random_pokemon = choice(available_pokemon)
        res['pokemon_id'] = random_pokemon.id
        
        # Set initial message
        res['result_message'] = f"A wild {random_pokemon.name} appeared!"
        
        return res
    
    @api.depends('pokemon_id')
    def _compute_pokemon_stats_display(self):
        """Display Pokemon stats in a nice format"""
        for wizard in self:
            if wizard.pokemon_id:
                stats = f"HP: {wizard.pokemon_id.base_hp}\n"
                stats += f"Attack: {wizard.pokemon_id.base_attack}\n"
                stats += f"Defense: {wizard.pokemon_id.base_defense}\n"
                stats += f"Speed: {wizard.pokemon_id.base_speed}"
                wizard.pokemon_stats_display = stats
            else:
                wizard.pokemon_stats_display = ""
    
    @api.depends('pokemon_id')
    def _compute_is_legendary(self):
        """Determine if a Pokemon is legendary based on stats"""
        for wizard in self:
            if wizard.pokemon_id:
                # Consider Pokemon legendary if total stats > 500
                total_stats = (wizard.pokemon_id.base_hp + 
                             wizard.pokemon_id.base_attack + 
                             wizard.pokemon_id.base_defense + 
                             wizard.pokemon_id.base_speed)
                
                # Also check specific Pokemon by name or pokedex number
                legendary_names = ['mewtwo', 'mew', 'articuno', 'zapdos', 'moltres', 
                                 'lugia', 'ho-oh', 'celebi', 'kyogre', 'groudon', 
                                 'rayquaza', 'dialga', 'palkia', 'giratina', 'arceus']
                legendary_numbers = [150, 151, 144, 145, 146, 249, 250, 251, 382, 383, 
                                   384, 483, 484, 487, 493]
                
                wizard.is_legendary = (total_stats > 500 or 
                                     wizard.pokemon_id.name.lower() in legendary_names or
                                     wizard.pokemon_id.pokedex_number in legendary_numbers)
            else:
                wizard.is_legendary = False
    
    @api.depends('pokemon_id', 'is_legendary')
    def _compute_catch_rate(self):
        """Calculate catch rate based on Pokemon stats"""
        for wizard in self:
            if wizard.pokemon_id:
                # Base catch rate starts at 90%
                base_rate = 90
                
                # Reduce based on total stats
                total_stats = (wizard.pokemon_id.base_hp + 
                             wizard.pokemon_id.base_attack + 
                             wizard.pokemon_id.base_defense + 
                             wizard.pokemon_id.base_speed)
                
                # Every 10 total stats reduces catch rate by 1%
                stats_penalty = total_stats // 10
                
                # Legendary Pokemon get an additional penalty
                legendary_penalty = 40 if wizard.is_legendary else 0
                
                # Calculate final catch rate (minimum 5%)
                catch_rate = max(5, base_rate - stats_penalty - legendary_penalty)
                
                wizard.catch_rate = catch_rate
            else:
                wizard.catch_rate = 0
    
    def attempt_catch(self):
        """Attempt to catch the randomly selected Pokemon"""
        self.ensure_one()
        
        if self.has_attempted:
            # Find a new Pokemon after an attempt
            return self.find_new_pokemon()
        
        # Check if trainer already has this Pokemon (double check)
        existing_pokemon = self.env['pokedex.trainer.pokemon'].search([
            ('trainer_id', '=', self.trainer_id.id),
            ('pokemon_id', '=', self.pokemon_id.id)
        ])
        
        if existing_pokemon:
            # This shouldn't happen with our default_get logic, but just in case
            return self.find_new_pokemon()
        
        # Roll for catch success based on calculated catch rate
        catch_roll = randint(1, 100)
        
        if catch_roll <= self.catch_rate:
            # Success! Create the trainer's Pokemon
            new_pokemon = self.env['pokedex.trainer.pokemon'].create({
                'trainer_id': self.trainer_id.id,
                'pokemon_id': self.pokemon_id.id,
                'nickname': False,  # No nickname by default
                'level': randint(3, 10),  # Random starting level between 3-10
                'experience': 0
            })
            
            self.catch_success = True
            
            # Special message for legendary Pokemon
            if self.is_legendary:
                self.result_message = f"INCREDIBLE! You caught the legendary {self.pokemon_id.name}!"
            else:
                self.result_message = f"Success! You caught {self.pokemon_id.name}!"
            
            self.has_attempted = True
            
            # Return a notification action
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pokemon Caught!',
                    'message': self.result_message,
                    'type': 'success',
                    'sticky': False,
                }
            }
        else:
            # Failed to catch
            self.catch_success = False
            
            # Different messages based on how close they were
            if catch_roll <= self.catch_rate + 10:
                self.result_message = f"So close! {self.pokemon_id.name} broke free at the last second!"
            elif self.is_legendary:
                self.result_message = f"The legendary {self.pokemon_id.name} broke free with its immense power!"
            else:
                self.result_message = f"Oh no! {self.pokemon_id.name} escaped!"
            
            self.has_attempted = True
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pokemon Escaped!',
                    'message': self.result_message,
                    'type': 'warning',
                    'sticky': False,
                }
            }
    
    def find_new_pokemon(self):
        """Find a new wild Pokemon"""
        # Get all Pokemon that the trainer doesn't already have
        owned_pokemon_ids = self.trainer_id.trainer_pokemon_ids.mapped('pokemon_id.id')
        
        # Find available Pokemon to catch (excluding current one if failed)
        domain = [('id', 'not in', owned_pokemon_ids)]
        if not self.catch_success and self.pokemon_id:
            domain.append(('id', '!=', self.pokemon_id.id))
        
        available_pokemon = self.env['pokedex.pokemon'].search(domain)
        
        if not available_pokemon:
            if self.catch_success:
                message = "Congratulations! You've caught all available Pokemon!"
            else:
                message = "No other Pokemon available right now. Try again later!"
            
            raise UserError(message)
        
        # Randomly select a new one
        new_pokemon = choice(available_pokemon)
        
        # Reset wizard state with new Pokemon
        self.write({
            'pokemon_id': new_pokemon.id,
            'has_attempted': False,
            'catch_success': False,
            'result_message': f"A wild {new_pokemon.name} appeared!"
        })
        
        # Reload the wizard
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pokedex.catch.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }