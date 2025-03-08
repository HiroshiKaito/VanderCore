import os
import logging
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

logger = logging.getLogger(__name__)

@dataclass
class Config:
    # Telegram Config
    TELEGRAM_TOKEN: str = None
    ADMIN_USER_ID: int = 0

    # Solana Config
    SOLANA_NETWORK: str = 'mainnet-beta'
    SOLANA_RPC_URL: str = 'https://api.mainnet-beta.solana.com'

    def __init__(self):
        """Initialize configuration with environment variables"""
        try:
            # Load Telegram configuration
            self.TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
            admin_id = os.environ.get('ADMIN_USER_ID', '0')

            try:
                self.ADMIN_USER_ID = int(admin_id)
            except ValueError:
                logger.error(f"Ungültige ADMIN_USER_ID: {admin_id}")
                raise ValueError("ADMIN_USER_ID muss eine gültige Zahl sein")

            # Load Solana configuration
            self.SOLANA_NETWORK = os.environ.get('SOLANA_NETWORK', self.SOLANA_NETWORK)
            self.SOLANA_RPC_URL = os.environ.get('SOLANA_RPC_URL', self.SOLANA_RPC_URL)

            self.validate_config()
            logger.info("Konfiguration erfolgreich geladen")

        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfiguration: {e}")
            raise

    def validate_config(self):
        """Validate the configuration values"""
        if not self.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN nicht gesetzt")

        # Admin ID ist optional
        if self.ADMIN_USER_ID != 0:
            if not isinstance(self.ADMIN_USER_ID, int):
                raise ValueError("ADMIN_USER_ID muss eine Zahl sein")

        if self.TELEGRAM_TOKEN and len(self.TELEGRAM_TOKEN) < 30:
            raise ValueError("TELEGRAM_TOKEN scheint ungültig zu sein (zu kurz)")

# Create a global instance
try:
    config = Config()
except Exception as e:
    logger.critical(f"Kritischer Fehler beim Erstellen der Konfiguration: {e}")
    # Don't raise here, let the bot handle missing configuration
    config = None