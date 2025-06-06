import requests
import logging
import base64
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class PokemonAPISync(models.Model):
    _name = 'pokedex.api.sync'
    _description = 'Pokemon API Synchronization'
    
    # This method gets a single Pokemon from the API using its name or ID
    @api.model
    def _get_pokemon_from_api(self, pokemon_name_or_id):
        try:
            url = f"https://pokeapi.co/api/v2/pokemon/{str(pokemon_name_or_id).lower()}"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching Pokemon data: {e}")
            raise UserError(f"Error connecting to PokeAPI: {e}")
    
    # This method gets species data (like descriptions) for a Pokemon
    @api.model
    def _get_pokemon_species_from_api(self, species_url):
        try:
            response = requests.get(species_url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching species data: {e}")
            raise UserError(f"Error connecting to PokeAPI: {e}")
    
    # This method gets all available Pokemon types
    @api.model
    def _get_types_from_api(self):
        try:
            url = "https://pokeapi.co/api/v2/type"
            response = requests.get(url)
            response.raise_for_status()
            return response.json()['results']
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching type data: {e}")
            raise UserError(f"Error connecting to PokeAPI: {e}")
    
    # This method gets detailed info about a specific type
    @api.model
    def _get_type_details_from_api(self, type_url):
        try:
            response = requests.get(type_url)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching type details: {e}")
            raise UserError(f"Error connecting to PokeAPI: {e}")
    
    # This is the main method that imports a Pokemon from the API to our database
    @api.model
    def import_pokemon(self, pokemon_name_or_id):
        pokemon_data = self._get_pokemon_from_api(pokemon_name_or_id)
        
        existing_pokemon = self.env['pokedex.pokemon'].search([
            ('pokedex_number', '=', pokemon_data['id'])
        ])
        
        if existing_pokemon:
            return existing_pokemon
        
        primary_type_name = pokemon_data['types'][0]['type']['name'].capitalize()
        primary_type = self.env['pokedex.type'].search([('name', '=', primary_type_name)], limit=1)
        
        if not primary_type:
            primary_type = self.env['pokedex.type'].create({
                'name': primary_type_name,
                'color': self._get_type_color(primary_type_name)  # Assign a color based on type
            })
        
        secondary_type = False
        if len(pokemon_data['types']) > 1:
            secondary_type_name = pokemon_data['types'][1]['type']['name'].capitalize()
            secondary_type = self.env['pokedex.type'].search([('name', '=', secondary_type_name)], limit=1)
            
            if not secondary_type:
                secondary_type = self.env['pokedex.type'].create({
                    'name': secondary_type_name,
                    'color': self._get_type_color(secondary_type_name)
                })
        
        skill_ids = []
        for move_data in pokemon_data['moves'][:4]:  # Just take the first 4 moves
            move_name = move_data['move']['name'].replace('-', ' ').title()
            skill = self.env['pokedex.skill'].search([('name', '=', move_name)], limit=1)
            
            if not skill:
                try:
                    move_url = move_data['move']['url']
                    move_response = requests.get(move_url)
                    move_response.raise_for_status()
                    move_details = move_response.json()
                    
                    move_type_name = move_details['type']['name'].capitalize()
                    move_type = self.env['pokedex.type'].search([('name', '=', move_type_name)], limit=1)
                    
                    if not move_type:
                        move_type = self.env['pokedex.type'].create({
                            'name': move_type_name,
                            'color': self._get_type_color(move_type_name)
                        })
                    
                    power = move_details.get('power', 0)
                    
                    skill = self.env['pokedex.skill'].create({
                        'name': move_name,
                        'type_id': move_type.id,
                        'power': power,
                        'description': move_details.get('flavor_text_entries', [{}])[0].get('flavor_text', 'No description available')
                    })
                    
                except requests.exceptions.RequestException:
                    skill = self.env['pokedex.skill'].create({
                        'name': move_name,
                        'type_id': primary_type.id,
                        'power': 50,
                        'description': 'No description available'
                    })
            
            skill_ids.append(skill.id)
        
        image_url = pokemon_data['sprites']['other']['official-artwork']['front_default']
        if not image_url:
            image_url = pokemon_data['sprites']['front_default']
        
        species_data = self._get_pokemon_species_from_api(pokemon_data['species']['url'])
        description = ""
        
        for entry in species_data.get('flavor_text_entries', []):
            if entry.get('language', {}).get('name') == 'en':
                description = entry.get('flavor_text', '').replace('\f', ' ').replace('\n', ' ')
                break
        
        new_pokemon = self.env['pokedex.pokemon'].create({
            'name': pokemon_data['name'].capitalize(),
            'pokedex_number': pokemon_data['id'],
            'type_id': primary_type.id,
            'secondary_type_id': secondary_type.id if secondary_type else False,
            'base_hp': pokemon_data['stats'][0]['base_stat'],
            'base_attack': pokemon_data['stats'][1]['base_stat'],
            'base_defense': pokemon_data['stats'][2]['base_stat'],
            'base_speed': pokemon_data['stats'][5]['base_stat'],
            'image_url': image_url,
            'description': description,
            'height': pokemon_data['height'] / 10,
            'weight': pokemon_data['weight'] / 10,
            'skill_ids': [(6, 0, skill_ids)]
        })
        
        return new_pokemon
    
    def _get_type_color(self, type_name):
        colors = {
            'Normal': '#A8A77A',
            'Fire': '#EE8130',
            'Water': '#6390F0',
            'Electric': '#F7D02C',
            'Grass': '#7AC74C',
            'Ice': '#96D9D6',
            'Fighting': '#C22E28',
            'Poison': '#A33EA1',
            'Ground': '#E2BF65',
            'Flying': '#A98FF3',
            'Psychic': '#F95587',
            'Bug': '#A6B91A',
            'Rock': '#B6A136',
            'Ghost': '#735797',
            'Dragon': '#6F35FC',
            'Dark': '#705746',
            'Steel': '#B7B7CE',
            'Fairy': '#D685AD',
        }
        return colors.get(type_name, '#777777')
    
    @api.model
    def sync_pokemon_batch(self, start_id, end_id):
        for pokemon_id in range(start_id, end_id + 1):
            try:
                self.import_pokemon(pokemon_id)
                import time
                time.sleep(0.5)
            except Exception as e:
                _logger.error(f"Error importing Pokemon {pokemon_id}: {e}")
                continue
        return True
    
    # This method imports all Pokemon types and their relationships
    @api.model
    def sync_all_types(self):
        types_data = self._get_types_from_api()
        
        for type_data in types_data:
            type_details = self._get_type_details_from_api(type_data['url'])
            type_name = type_details['name'].capitalize()
            
            existing_type = self.env['pokedex.type'].search([('name', '=', type_name)], limit=1)
            
            if existing_type:
                type_id = existing_type.id
            else:
                new_type = self.env['pokedex.type'].create({
                    'name': type_name,
                    'color': self._get_type_color(type_name)
                })
                type_id = new_type.id
        
        for type_data in types_data:
            type_details = self._get_type_details_from_api(type_data['url'])
            type_name = type_details['name'].capitalize()
            
            type_record = self.env['pokedex.type'].search([('name', '=', type_name)], limit=1)
            
            if not type_record:
                continue
                
            strength_against_ids = []
            for double_damage_to in type_details['damage_relations']['double_damage_to']:
                target_type = self.env['pokedex.type'].search(
                    [('name', '=', double_damage_to['name'].capitalize())], limit=1
                )
                if target_type:
                    strength_against_ids.append(target_type.id)
                    
            weakness_against_ids = []
            for double_damage_from in type_details['damage_relations']['double_damage_from']:
                source_type = self.env['pokedex.type'].search(
                    [('name', '=', double_damage_from['name'].capitalize())], limit=1
                )
                if source_type:
                    weakness_against_ids.append(source_type.id)
                    
            type_record.write({
                'strength_against': [(6, 0, strength_against_ids)],
                'weakness_against': [(6, 0, weakness_against_ids)]
            })
            
        return True