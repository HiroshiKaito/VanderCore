import logging
from flask import Flask, jsonify
import nltk
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

# Download required NLTK data
try:
    logger.info("Downloading required NLTK data...")
    nltk.download(['punkt', 'averaged_perceptron_tagger', 'vader_lexicon'])
    logger.info("NLTK data download completed")
except Exception as e:
    logger.error(f"Failed to download NLTK data: {e}")

# Root route to confirm server is running
@app.route('/')
def root():
    return jsonify({
        'status': 'running',
        'message': 'Solana Trading Bot Server is running'
    })

if __name__ == "__main__":
    # This is used when running locally
    app.run(host='0.0.0.0', port=5000, debug=False)