"""
Configuration settings for ProductSync
"""

import os
from typing import Optional

class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    FLASK_HOST = os.getenv('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(os.getenv('FLASK_PORT', 5000))
    FLASK_DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    
    # Database settings
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://localhost/productsync')
    
    # Redis settings
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # Discord settings
    DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
    DISCORD_GUILD_ID = os.getenv('DISCORD_GUILD_ID')
    
    # Slack settings
    SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
    SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
    
    # Notion settings
    NOTION_TOKEN = os.getenv('NOTION_TOKEN')
    NOTION_DATABASE_ID = os.getenv('NOTION_DATABASE_ID')
    
    # JIRA settings
    JIRA_URL = os.getenv('JIRA_URL')
    JIRA_USERNAME = os.getenv('JIRA_USERNAME')
    JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')
    
    # NLP settings
    SPACY_MODEL = os.getenv('SPACY_MODEL', 'en_core_web_md')
    TRANSFORMERS_CACHE_DIR = os.getenv('TRANSFORMERS_CACHE_DIR', './models')
    
    # Celery settings
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/2')
    
    # Priority scoring weights
    PRIORITY_WEIGHTS = {
        'severity': 0.3,
        'reach': 0.25,
        'novelty': 0.2,
        'momentum': 0.15,
        'confidence': 0.1
    }
    
    # Thresholds
    PRIORITY_THRESHOLD = float(os.getenv('PRIORITY_THRESHOLD', '0.7'))
    CLUSTER_MIN_SIZE = int(os.getenv('CLUSTER_MIN_SIZE', '3'))
    
    @classmethod
    def validate(cls) -> list[str]:
        """Validate required configuration."""
        errors = []
        
        if not cls.DISCORD_TOKEN:
            errors.append("DISCORD_TOKEN is required")
        
        if not cls.DATABASE_URL:
            errors.append("DATABASE_URL is required")
        
        if not cls.REDIS_URL:
            errors.append("REDIS_URL is required")
        
        return errors

class DevelopmentConfig(Config):
    """Development configuration."""
    FLASK_DEBUG = True
    CELERY_TASK_ALWAYS_EAGER = True

class ProductionConfig(Config):
    """Production configuration."""
    FLASK_DEBUG = False
    CELERY_TASK_ALWAYS_EAGER = False

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    DATABASE_URL = os.getenv('TEST_DATABASE_URL', 'postgresql://localhost/productsync_test')
    CELERY_TASK_ALWAYS_EAGER = True

# Configuration mapping
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name: Optional[str] = None) -> Config:
    """Get configuration instance."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'default')
    
    return config.get(config_name, config['default']) 