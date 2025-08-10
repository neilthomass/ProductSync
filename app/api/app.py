from flask import Flask
from flask_cors import CORS
import logging
from app.api.routes import feedback_bp, slack_bp, discord_bp, notion_bp

def create_app(config_name='development'):
    """Application factory for Flask app."""
    app = Flask(__name__)

    if config_name == 'testing':
        app.config['TESTING'] = True
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    # Enable CORS
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(feedback_bp, url_prefix='/api/feedback')
    app.register_blueprint(slack_bp, url_prefix='/api/slack')
    app.register_blueprint(discord_bp, url_prefix='/api/discord')
    app.register_blueprint(notion_bp, url_prefix='/api/notion')
    
    # Health check endpoint
    @app.route('/health')
    def health():
        return {'status': 'healthy', 'service': 'ProductSync API'}
    
    # Error handlers
    @app.errorhandler(404)
    def not_found(error):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(error):
        return {'error': 'Internal server error'}, 500

    return app
