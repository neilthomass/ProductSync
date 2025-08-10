#!/usr/bin/env python3
"""
ProductSync - Main application entry point
Runs both the Flask API and Discord bot
"""

import os
import logging
import threading
import time
from dotenv import load_dotenv
from app.api.app import create_app
from app.bots.discord_bot import run_discord_bot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_flask_api():
    """Run the Flask API server."""
    try:
        app = create_app()
        host = os.getenv('FLASK_HOST', '0.0.0.0')
        port = int(os.getenv('FLASK_PORT', 5000))
        debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        
        logger.info(f"Starting Flask API server on {host}:{port}")
        app.run(host=host, port=port, debug=debug, use_reloader=False)
    except Exception as e:
        logger.error(f"Failed to start Flask API: {e}")

def start_discord_bot():
    """Run the Discord bot."""
    try:
        logger.info("Starting Discord bot")
        run_discord_bot()
    except Exception as e:
        logger.error(f"Failed to start Discord bot: {e}")

def main():
    """Main application entry point."""
    logger.info("Starting ProductSync application...")
    
    # Check required environment variables
    required_env_vars = ['REDIS_URL', 'DATABASE_URL']
    missing_vars = [var for var in required_env_vars if not os.getenv(var)]
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        logger.error("Please set the required environment variables and try again.")
        return
    
    # Start Flask API in a separate thread
    flask_thread = threading.Thread(target=run_flask_api, daemon=True)
    flask_thread.start()
    
    # Give Flask a moment to start
    time.sleep(2)
    
    # Start Discord bot in main thread
    try:
        start_discord_bot()
    except KeyboardInterrupt:
        logger.info("Shutting down ProductSync...")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    main()
