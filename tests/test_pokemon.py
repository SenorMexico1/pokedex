from odoo.tests import common
from odoo.exceptions import UserError

class TestPokemon(common.TransactionCase):
    
    def setUp(self):
        """Set up test data"""
        super(TestPokemon, self).setUp()
        
        # Types test
        self.type_fire = self.env['pokedex.type'].create({
            'name': 'Fire',
            'color': '#EE8130'
        })
        
        self.type_flying = self.env['pokedex.type'].create({
            'name': 'Flying',
            'color': '#A98FF3'
        })
        
        # Skills test
        self.skill_ember = self.env['pokedex.skill'].create({
            'name': 'Ember',
            'type_id': self.type_fire.id,
            'power': 40,
            'description': 'A basic fire attack'
        })
        
        # Pokemon test
        self.pokemon_charmander = self.env['pokedex.pokemon'].create({
            'name': 'Charmander',
            'pokedex_number': 4,
            'type_id': self.type_fire.id,
            'base_hp': 39,
            'base_attack': 52,
            'base_defense': 43,
            'base_speed': 65,
            'skill_ids': [(4, self.skill_ember.id)]
        })
        
        # Trainer test
        self.trainer = self.env['res.partner'].create({
            'name': 'Ash Ketchum',
            'is_trainer': True
        })
    
    def test_pokemon_creation(self):
        """Test Pokemon creation"""
        # Pokemon creation check
        self.assertEqual(self.pokemon_charmander.name, 'Charmander')
        self.assertEqual(self.pokemon_charmander.pokedex_number, 4)
        self.assertEqual(self.pokemon_charmander.type_id.name, 'Fire')
        self.assertEqual(self.pokemon_charmander.base_hp, 39)
        
        # Is the skill linked?
        self.assertIn(self.skill_ember, self.pokemon_charmander.skill_ids)
    
    def test_trainer_pokemon_creation(self):
        """Test creating a trainer's Pokemon"""
        # Create a trainer's Pokemon
        trainer_pokemon = self.env['pokedex.trainer.pokemon'].create({
            'trainer_id': self.trainer.id,
            'pokemon_id': self.pokemon_charmander.id,
            'nickname': 'Char',
            'level': 5,
            'experience': 0
        })
        
        # Check creation
        self.assertEqual(trainer_pokemon.trainer_id.id, self.trainer.id)
        self.assertEqual(trainer_pokemon.pokemon_id.id, self.pokemon_charmander.id)
        self.assertEqual(trainer_pokemon.nickname, 'Char')
        self.assertEqual(trainer_pokemon.level, 5)
        
        # Check computed stats
        expected_hp = self.pokemon_charmander.base_hp + (5 * 5)
        self.assertEqual(trainer_pokemon.hp, expected_hp)
    
    def test_pokemon_count_computation(self):
        """Test trainer's Pokemon count computation"""

        # Checks trainers initial Pokemon count
        self.assertEqual(self.trainer.pokemon_count, 0)
        
        # Add a Pokemon to created trainer
        self.env['pokedex.trainer.pokemon'].create({
            'trainer_id': self.trainer.id,
            'pokemon_id': self.pokemon_charmander.id,
            'level': 5
        })
        
        # Checks the updated Pokemon count
        self.assertEqual(self.trainer.pokemon_count, 1)
    
    def test_level_up(self):
        """Test Pokemon level up functionality"""
        # Create trainer's Pokemon
        trainer_pokemon = self.env['pokedex.trainer.pokemon'].create({
            'trainer_id': self.trainer.id,
            'pokemon_id': self.pokemon_charmander.id,
            'level': 5,
            'experience': 0
        })
        
        # Record initial stats
        initial_hp = trainer_pokemon.hp
        initial_attack = trainer_pokemon.attack
        
        # Level up
        trainer_pokemon.level_up()
        
        # Check increased leve
        self.assertEqual(trainer_pokemon.level, 6)
        
        # Check increased stats
        self.assertGreater(trainer_pokemon.hp, initial_hp)
        self.assertGreater(trainer_pokemon.attack, initial_attack)
    
    def test_catch_wizard(self):
        """Test the catch Pokemon wizard"""
        # Create catch wizard
        wizard = self.env['pokedex.catch.wizard'].create({
            'trainer_id': self.trainer.id,
            'pokemon_id': self.pokemon_charmander.id
        })
        
        # Check created wizard
        self.assertEqual(wizard.trainer_id.id, self.trainer.id)
        self.assertEqual(wizard.pokemon_id.id, self.pokemon_charmander.id)
        
        self.assertTrue(wizard.exists())
    
    def test_type_relationships(self):
        """Test Pokemon type strength/weakness relationships"""
        # Set up type relationships
        self.type_fire.write({
            'weakness_against': [(4, self.type_flying.id)]
        })
        
        # Check relationships
        self.assertIn(self.type_flying, self.type_fire.weakness_against)
    
    def test_api_sync_model(self):
        """Test API sync model exists and has required methods"""
        api_sync = self.env['pokedex.api.sync']
        
        # Checks if the model exists
        self.assertTrue(hasattr(api_sync, '_get_pokemon_from_api'))
        self.assertTrue(hasattr(api_sync, 'import_pokemon'))
        self.assertTrue(hasattr(api_sync, '_get_type_color'))
    
    def test_experience_cron_model(self):
        """Test experience cron model exists"""
        exp_cron = self.env['pokedex.experience.cron']
        
        # Checks if the model exists and has the award experience method
        self.assertTrue(hasattr(exp_cron, '_award_experience'))