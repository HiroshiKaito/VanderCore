
import logging
from flask import Flask
from bot import TelegramBot
import os

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

# Create Flask app
app = Flask(__name__)

# Set secret key from environment
app.secret_key = os.environ.get('SESSION_SECRET', 'default_secret_key_for_development')

# Initialize bot instance
bot_instance = None

try:
    logger.info("Initializing TelegramBot instance for webhook mode")
    bot_instance = TelegramBot()
except Exception as e:
    logger.error(f"Failed to initialize bot: {e}")

@app.route('/')
def index():
    return "Bot server is running"

@app.route('/health')
def health():
    if bot_instance:
        return "OK", 200
    return "Bot not initialized", 500

if __name__ == "__main__":
    # This is used when running locally
    app.run(host='0.0.0.0', port=5000, debug=False)
