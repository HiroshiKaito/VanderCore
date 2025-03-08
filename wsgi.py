import logging
import os
from flask import Flask, jsonify

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("webhook_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Import the Flask app from webhook_bot.py
from webhook_bot import app, setup_bot, get_bot_info

# Initialize bot
if not setup_bot():
    logger.critical("Bot-Initialisierung fehlgeschlagen. Überprüfen Sie die Umgebungsvariablen.")

@app.route('/')
def root():
    """Root route to confirm server is running"""
    try:
        bot_info = get_bot_info()
        return jsonify({
            'status': 'running',
            'message': 'Solana Trading Bot Server is running',
            'bot_info': bot_info.username if bot_info else None
        })
    except Exception as e:
        logger.error(f"Error in root route: {e}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)