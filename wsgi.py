import logging
from webhook_bot import app

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

# Die Flask-App wurde bereits in webhook_bot.py initialisiert und wird hier importiert

if __name__ == "__main__":
    # This is used when running locally
    app.run(host='0.0.0.0', port=5000, debug=False)