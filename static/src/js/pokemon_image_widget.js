odoo.define('pokedex_app.pokemon_image_widget', function (require) {
    "use strict";
    
    var AbstractField = require('web.AbstractField');
    var fieldRegistry = require('web.field_registry');
    
    // Create a custom widget to display Pokemon images
    var PokemonImageWidget = AbstractField.extend({
        template: 'PokemonImageWidget',
        supportedFieldTypes: ['char'],
        
        /**
         * Initialize the widget
         */
        init: function () {
            this._super.apply(this, arguments);
            this.imageUrl = false;
        },
        
        /**
         * Start the widget
         */
        start: function () {
            var self = this;
            return this._super.apply(this, arguments).then(function () {
                self._render();
            });
        },
        
        /**
         * Render the widget
         */
        _render: function () {
            var self = this;
            this.imageUrl = this.value || false;
            
            if (this.imageUrl) {
                this.$el.empty();
                var $img = $('<img>').attr({
                    'src': this.imageUrl,
                    'class': 'pokemon-image',
                    'alt': 'Pokemon Image'
                });
                
                // Handle image loading errors
                $img.on('error', function () {
                    $(this).attr('src', '/pokedex_app/static/description/icon.png');
                });
                
                this.$el.append($img);
            } else {
                this.$el.html('<span class="text-muted">No image</span>');
            }
        },
        
        /**
         * Update the value and re-render
         */
        _setValue: function (value) {
            this._super.apply(this, arguments);
            this._render();
        }
    });
    
    // Register the widget
    fieldRegistry.add('pokedex_image', PokemonImageWidget);
    
    return PokemonImageWidget;
});