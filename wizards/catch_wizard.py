# wizards/catch_wizard.py - Debug version to see what's happening

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
    result_message = fields.Char(string='Result', readonly=True, default="Searching for wild Pokemon...")
    
    # State to track if we've attempted to catch
    has_attempted = fields.Boolean(string='Has Attempted', default=False)
    
    # Debug field
    debug_info = fields.Text(string='Debug Info', compute='_compute_debug_info')
    
    @api.depends('pokemon_id', 'has_attempted', 'result_message')
    def _compute_debug_info(self):
        for wizard in self:
            wizard.debug_info = f"""
            Pokemon ID: {wizard.pokemon_id.id if wizard.pokemon_id else 'None'}
            Pokemon Name: {wizard.pokemon_id.name if wizard.pokemon_id else 'None'}
            Has Attempted: {wizard.has_attempted}
            Result Message: {wizard.result_message}
            Context: {self.env.context}
            """
    
    @api.model
    def default_get(self, fields_list):
        """Override to randomly select a Pokemon when wizard opens"""
        res = super().default_get(fields_list)
        
        _logger.info(f"=== CATCH WIZARD DEFAULT_GET ===")
        _logger.info(f"Context: {self.env.context}")
        _logger.info(f"Fields list: {fields_list}")
        
        # Set the default trainer if not provided
        trainer_id = res.get('trainer_id') or self.env.context.get('default_trainer_id') or self.env.user.partner_id.id
        res['trainer_id'] = trainer_id
        
        # Get the trainer
        trainer = self.env['res.partner'].browse(trainer_id)
        if not trainer.exists():
            trainer = self.env.user.partner_id
            res['trainer_id'] = trainer.id
        
        # Get all Pokemon that the trainer doesn't already have
        owned_pokemon_ids = trainer.trainer_pokemon_ids.mapped('pokemon_id.id')
        
        # Find available Pokemon to catch
        available_pokemon = self.env['pokedex.pokemon'].search([
            ('id', 'not in', owned_pokemon_ids)
        ])
        
        if not available_pokemon:
            res['result_message'] = "Congratulations! You've already caught all available Pokemon!"
            return res
        
        # Randomly select one
        random_pokemon = choice(available_pokemon)
        res['pokemon_id'] = random_pokemon.id
        # IMPORTANT: Include the Pokemon ID in the message so we can parse it later
        res['result_message'] = f"A wild {random_pokemon.name} (#{random_pokemon.pokedex_number}) appeared!"
        
        _logger.info(f"Selected Pokemon: {random_pokemon.name} (ID: {random_pokemon.id}, Number: {random_pokemon.pokedex_number})")
        _logger.info(f"Result dict: {res}")
        
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
                total_stats = (wizard.pokemon_id.base_hp + 
                             wizard.pokemon_id.base_attack + 
                             wizard.pokemon_id.base_defense + 
                             wizard.pokemon_id.base_speed)
                
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
                base_rate = 90
                total_stats = (wizard.pokemon_id.base_hp + 
                             wizard.pokemon_id.base_attack + 
                             wizard.pokemon_id.base_defense + 
                             wizard.pokemon_id.base_speed)
                stats_penalty = total_stats // 10
                legendary_penalty = 40 if wizard.is_legendary else 0
                catch_rate = max(5, base_rate - stats_penalty - legendary_penalty)
                wizard.catch_rate = catch_rate
            else:
                wizard.catch_rate = 0
    
    def attempt_catch(self):
        """Attempt to catch the randomly selected Pokemon"""
        self.ensure_one()
        
        _logger.info(f"=== ATTEMPT CATCH ===")
        _logger.info(f"Current state - Has attempted: {self.has_attempted}")
        _logger.info(f"Current Pokemon ID field: {self.pokemon_id.id if self.pokemon_id else 'None'}")
        _logger.info(f"Current Pokemon Name field: {self.pokemon_id.name if self.pokemon_id else 'None'}")
        _logger.info(f"Result message: {self.result_message}")
        
        if self.has_attempted:
            # Find a new Pokemon after an attempt
            return self.find_new_pokemon()
        
        # BETTER FIX: Parse the Pokemon NAME from the result_message
        import re
        name_match = re.search(r"A wild (.+) \(#\d+\) appeared!", self.result_message or "")
        if not name_match:
            raise UserError("Could not determine which Pokemon to catch!")
        
        pokemon_name = name_match.group(1)
        
        # Find the Pokemon by its name (more reliable than number)
        pokemon = self.env['pokedex.pokemon'].search([
            ('name', '=', pokemon_name)
        ], limit=1)
        
        if not pokemon:
            # Try case-insensitive search
            pokemon = self.env['pokedex.pokemon'].search([
                ('name', 'ilike', pokemon_name)
            ], limit=1)
        
        if not pokemon:
            raise UserError(f"Could not find Pokemon named '{pokemon_name}'!")
        
        _logger.info(f"Found Pokemon by name: {pokemon.name} (Pokedex #{pokemon.pokedex_number}, DB ID: {pokemon.id})")
        _logger.info(f"This is the Pokemon we will actually try to catch!")
        
        # Store the Pokemon info - USE THE POKEMON WE JUST FOUND
        pokemon_name = pokemon.name
        pokemon_id = pokemon.id
        
        # Calculate catch rate for THIS Pokemon
        total_stats = (pokemon.base_hp + pokemon.base_attack + 
                      pokemon.base_defense + pokemon.base_speed)
        
        # Check if legendary
        legendary_names = ['mewtwo', 'mew', 'articuno', 'zapdos', 'moltres', 
                         'lugia', 'ho-oh', 'celebi', 'kyogre', 'groudon', 
                         'rayquaza', 'dialga', 'palkia', 'giratina', 'arceus']
        legendary_numbers = [150, 151, 144, 145, 146, 249, 250, 251, 382, 383, 
                           384, 483, 484, 487, 493]
        
        pokemon_is_legendary = (total_stats > 500 or 
                               pokemon.name.lower() in legendary_names or
                               pokemon.pokedex_number in legendary_numbers)
        
        # Calculate catch rate
        base_rate = 90
        stats_penalty = total_stats // 10
        legendary_penalty = 40 if pokemon_is_legendary else 0
        catch_rate = max(5, base_rate - stats_penalty - legendary_penalty)
        
        _logger.info(f"Calculated catch rate: {catch_rate}% for {pokemon_name}")
        
        # Check if trainer already has this Pokemon
        existing_pokemon = self.env['pokedex.trainer.pokemon'].search([
            ('trainer_id', '=', self.trainer_id.id),
            ('pokemon_id', '=', pokemon_id)
        ])
        
        if existing_pokemon:
            _logger.warning(f"Trainer already has {pokemon_name}")
            return self.find_new_pokemon()
        
        # Roll for catch success
        catch_roll = randint(1, 100)
        _logger.info(f"Catch roll: {catch_roll} vs catch rate: {catch_rate}")
        
        if catch_roll <= catch_rate:
            # Success!
            try:
                new_pokemon = self.env['pokedex.trainer.pokemon'].create({
                    'trainer_id': self.trainer_id.id,
                    'pokemon_id': pokemon_id,
                    'nickname': False,
                    'level': randint(3, 10),
                    'experience': 0
                })
                
                self.write({
                    'catch_success': True,
                    'has_attempted': True
                })
                
                if pokemon_is_legendary:
                    success_message = f"INCREDIBLE! You caught the legendary {pokemon_name}!"
                else:
                    success_message = f"Success! You caught {pokemon_name}!"
                
                self.result_message = success_message
                
                return {
                    'type': 'ir.actions.client',
                    'tag': 'display_notification',
                    'params': {
                        'title': 'Pokemon Caught!',
                        'message': success_message,
                        'type': 'success',
                        'sticky': False,
                    }
                }
            except Exception as e:
                _logger.error(f"Error creating trainer pokemon: {str(e)}")
                raise UserError(f"Error catching Pokemon: {str(e)}")
        else:
            # Failed
            if catch_roll <= catch_rate + 10:
                failure_message = f"So close! {pokemon_name} broke free at the last second!"
            elif pokemon_is_legendary:
                failure_message = f"The legendary {pokemon_name} broke free with its immense power!"
            else:
                failure_message = f"Oh no! {pokemon_name} escaped!"
            
            self.write({
                'catch_success': False,
                'result_message': failure_message,
                'has_attempted': True
            })
            
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Pokemon Escaped!',
                    'message': failure_message,
                    'type': 'warning',
                    'sticky': False,
                }
            }
    
    def find_new_pokemon(self):
        """Find a new wild Pokemon"""
        _logger.info("=== FIND NEW POKEMON ===")
        
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
        
        _logger.info(f"New Pokemon selected: {new_pokemon.name} (ID: {new_pokemon.id})")
        
        # Reset wizard state
        self.write({
            'pokemon_id': new_pokemon.id,
            'has_attempted': False,
            'catch_success': False,
            'result_message': f"A wild {new_pokemon.name} (#{new_pokemon.pokedex_number}) appeared!"
        })
        
        # Reload the wizard
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'pokedex.catch.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }