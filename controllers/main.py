from odoo import http
from odoo.http import request
import json

class PokedexController(http.Controller):
    
    # GET endpoint - View all Pokemon (HTML)
    @http.route('/pokedex/pokemon', type='http', auth='public', methods=['GET'])
    def get_all_pokemon_html(self):
        """Get all Pokemon and display as HTML"""
        pokemon_records = request.env['pokedex.pokemon'].sudo().search([])
        
        html_result = """
        <html>
            <head>
                <title>Pokedex - All Pokemon</title>
                <style>
                    body { font-family: Arial, sans-serif; }
                    .pokemon-list { list-style: none; padding: 0; }
                    .pokemon-item { 
                        margin: 10px; 
                        padding: 10px; 
                        border: 1px solid #ddd; 
                        border-radius: 5px;
                    }
                </style>
            </head>
            <body>
                <h1>All Pokemon in Pokedex</h1>
                <ul class="pokemon-list">
        """
        
        for pokemon in pokemon_records:
            html_result += f"""
                <li class="pokemon-item">
                    <strong>#{pokemon.pokedex_number} - {pokemon.name}</strong><br>
                    Type: {pokemon.type_id.name}
                    {f' / {pokemon.secondary_type_id.name}' if pokemon.secondary_type_id else ''}<br>
                    HP: {pokemon.base_hp} | Attack: {pokemon.base_attack}
                </li>
            """
        
        html_result += """
                </ul>
            </body>
        </html>
        """
        
        return html_result
    
    # GET endpoint - View single Pokemon (JSON)
    @http.route('/api/pokedex/pokemon/<int:pokemon_id>', type='json', auth='public', methods=['GET'])
    def get_pokemon_json(self, pokemon_id):
        """Get a single Pokemon by ID and return as JSON"""
        pokemon = request.env['pokedex.pokemon'].sudo().browse(pokemon_id)
        
        if not pokemon.exists():
            return {'error': 'Pokemon not found', 'status': 404}
        
        return {
            'id': pokemon.id,
            'name': pokemon.name,
            'pokedex_number': pokemon.pokedex_number,
            'type': pokemon.type_id.name,
            'secondary_type': pokemon.secondary_type_id.name if pokemon.secondary_type_id else None,
            'stats': {
                'hp': pokemon.base_hp,
                'attack': pokemon.base_attack,
                'defense': pokemon.base_defense,
                'speed': pokemon.base_speed
            },
            'height': pokemon.height,
            'weight': pokemon.weight,
            'description': pokemon.description
        }
    
    # GET endpoint - View all Pokemon (JSON)
    @http.route('/api/pokedex/pokemon', type='json', auth='public', methods=['GET'])
    def get_all_pokemon_json(self):
        """Get all Pokemon and return as JSON"""
        pokemon_records = request.env['pokedex.pokemon'].sudo().search([])
        
        pokemon_list = []
        for pokemon in pokemon_records:
            pokemon_list.append({
                'id': pokemon.id,
                'name': pokemon.name,
                'pokedex_number': pokemon.pokedex_number,
                'type': pokemon.type_id.name,
                'secondary_type': pokemon.secondary_type_id.name if pokemon.secondary_type_id else None
            })
        
        return {
            'count': len(pokemon_list),
            'pokemon': pokemon_list
        }
    
    # POST endpoint - Create new Pokemon
    @http.route('/api/pokedex/pokemon', type='json', auth='user', methods=['POST'])
    def create_pokemon(self, **kwargs):
        """Create a new Pokemon"""
        try:
            # Get required fields
            required_fields = ['name', 'pokedex_number', 'type_id']
            for field in required_fields:
                if field not in kwargs:
                    return {'error': f'Missing required field: {field}', 'status': 400}
            
            # Create the Pokemon
            new_pokemon = request.env['pokedex.pokemon'].create({
                'name': kwargs.get('name'),
                'pokedex_number': kwargs.get('pokedex_number'),
                'type_id': kwargs.get('type_id'),
                'secondary_type_id': kwargs.get('secondary_type_id', False),
                'base_hp': kwargs.get('base_hp', 100),
                'base_attack': kwargs.get('base_attack', 50),
                'base_defense': kwargs.get('base_defense', 50),
                'base_speed': kwargs.get('base_speed', 50),
                'height': kwargs.get('height', 1.0),
                'weight': kwargs.get('weight', 10.0),
                'description': kwargs.get('description', '')
            })
            
            return {
                'success': True,
                'id': new_pokemon.id,
                'message': f'Pokemon {new_pokemon.name} created successfully!'
            }
            
        except Exception as e:
            return {'error': str(e), 'status': 500}
    
    # PUT endpoint - Update Pokemon
    @http.route('/api/pokedex/pokemon/<int:pokemon_id>', type='json', auth='user', methods=['PUT'])
    def update_pokemon(self, pokemon_id, **kwargs):
        """Update an existing Pokemon"""
        try:
            pokemon = request.env['pokedex.pokemon'].browse(pokemon_id)
            
            if not pokemon.exists():
                return {'error': 'Pokemon not found', 'status': 404}
            
            # Update fields that are provided
            update_vals = {}
            allowed_fields = ['name', 'type_id', 'secondary_type_id', 'base_hp', 
                            'base_attack', 'base_defense', 'base_speed', 
                            'height', 'weight', 'description']
            
            for field in allowed_fields:
                if field in kwargs:
                    update_vals[field] = kwargs[field]
            
            pokemon.write(update_vals)
            
            return {
                'success': True,
                'message': f'Pokemon {pokemon.name} updated successfully!'
            }
            
        except Exception as e:
            return {'error': str(e), 'status': 500}
    
    # DELETE endpoint - Delete Pokemon
    @http.route('/api/pokedex/pokemon/<int:pokemon_id>', type='json', auth='user', methods=['DELETE'])
    def delete_pokemon(self, pokemon_id):
        """Delete a Pokemon"""
        try:
            pokemon = request.env['pokedex.pokemon'].browse(pokemon_id)
            
            if not pokemon.exists():
                return {'error': 'Pokemon not found', 'status': 404}
            
            pokemon_name = pokemon.name
            pokemon.unlink()
            
            return {
                'success': True,
                'message': f'Pokemon {pokemon_name} deleted successfully!'
            }
            
        except Exception as e:
            return {'error': str(e), 'status': 500}
    
    # Trainer endpoints
    @http.route('/api/pokedex/trainers', type='json', auth='public', methods=['GET'])
    def get_all_trainers(self):
        """Get all trainers"""
        trainers = request.env['res.partner'].sudo().search([('is_trainer', '=', True)])
        
        trainer_list = []
        for trainer in trainers:
            trainer_list.append({
                'id': trainer.id,
                'name': trainer.name,
                'trainer_level': trainer.trainer_level,
                'pokemon_count': trainer.pokemon_count,
                'pokemon': [{
                    'id': p.id,
                    'name': p.pokemon_id.name,
                    'level': p.level,
                    'nickname': p.nickname or p.pokemon_id.name
                } for p in trainer.trainer_pokemon_ids]
            })
        
        return {
            'count': len(trainer_list),
            'trainers': trainer_list
        }
    
    # Trainer's Pokemon endpoint
    @http.route('/api/pokedex/trainer/<int:trainer_id>/pokemon', type='json', auth='public', methods=['GET'])
    def get_trainer_pokemon(self, trainer_id):
        """Get all Pokemon belonging to a specific trainer"""
        trainer = request.env['res.partner'].sudo().browse(trainer_id)
        
        if not trainer.exists() or not trainer.is_trainer:
            return {'error': 'Trainer not found', 'status': 404}
        
        pokemon_list = []
        for trainer_pokemon in trainer.trainer_pokemon_ids:
            pokemon_list.append({
                'id': trainer_pokemon.id,
                'pokemon_name': trainer_pokemon.pokemon_id.name,
                'nickname': trainer_pokemon.nickname,
                'level': trainer_pokemon.level,
                'experience': trainer_pokemon.experience,
                'stats': {
                    'hp': trainer_pokemon.hp,
                    'attack': trainer_pokemon.attack,
                    'defense': trainer_pokemon.defense,
                    'speed': trainer_pokemon.speed
                }
            })
        
        return {
            'trainer': trainer.name,
            'pokemon_count': len(pokemon_list),
            'pokemon': pokemon_list
        }