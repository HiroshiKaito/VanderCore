import logging
from flask import Flask, jsonify
from config import config
from webhook_bot import app, setup_bot

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.DEBUG,  # Erhöhtes Log-Level für bessere Fehleranalyse
    handlers=[
        logging.FileHandler("wsgi.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize bot
try:
    logger.debug("Starting bot initialization...")
    if not setup_bot():
        logger.critical("Bot-Initialisierung fehlgeschlagen. Überprüfen Sie die Umgebungsvariablen.")
        raise RuntimeError("Bot setup failed")
    logger.info("Bot successfully initialized")
except Exception as e:
    logger.critical(f"Critical error during bot initialization: {e}", exc_info=True)
    raise

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)