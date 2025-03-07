import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class Config:
    # Telegram Config
    TELEGRAM_TOKEN: str = None
    ADMIN_USER_ID: int = 0

    # Solana Config
    SOLANA_NETWORK: str = 'mainnet-beta'
    SOLANA_RPC_URL: str = 'https://api.mainnet-beta.solana.com'

    # Optional: Custom RPC URLs for different networks
    RPC_URLS = {
        'devnet': 'https://api.devnet.solana.com',
        'mainnet-beta': 'https://api.mainnet-beta.solana.com'
    }

    def __init__(self):
        """Initialize configuration with environment variables"""
        try:
            # Load Telegram configuration
            self.TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
            admin_id = os.environ.get('ADMIN_USER_ID', '0')

            logger.info("Lade Konfiguration...")
            logger.debug(f"Token gefunden: {'Ja' if self.TELEGRAM_TOKEN else 'Nein'}")
            logger.debug(f"Admin ID gefunden: {'Ja' if admin_id != '0' else 'Nein'}")

            try:
                self.ADMIN_USER_ID = int(admin_id)
            except ValueError:
                logger.error(f"Ungültige ADMIN_USER_ID: {admin_id}")
                raise ValueError("ADMIN_USER_ID muss eine gültige Zahl sein")

            # Load Solana configuration
            self.SOLANA_NETWORK = os.environ.get('SOLANA_NETWORK', self.SOLANA_NETWORK)
            self.SOLANA_RPC_URL = os.environ.get('SOLANA_RPC_URL', self.RPC_URLS[self.SOLANA_NETWORK])

            self.validate_config()
            logger.info("Konfiguration erfolgreich geladen")

        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfiguration: {e}")
            raise

    def validate_config(self):
        """Validate the configuration values"""
        if not self.TELEGRAM_TOKEN:
            raise ValueError("TELEGRAM_TOKEN nicht gesetzt")

        if self.ADMIN_USER_ID == 0:
            raise ValueError("ADMIN_USER_ID nicht gesetzt")

        if not isinstance(self.ADMIN_USER_ID, int):
            raise ValueError("ADMIN_USER_ID muss eine Zahl sein")

        if len(self.TELEGRAM_TOKEN) < 30:
            raise ValueError("TELEGRAM_TOKEN scheint ungültig zu sein (zu kurz)")

        logger.info("Konfiguration validiert")
        logger.debug(f"Admin User ID: {self.ADMIN_USER_ID}")
        logger.debug(f"Token Länge: {len(self.TELEGRAM_TOKEN)}")
        logger.debug(f"Solana Network: {self.SOLANA_NETWORK}")
        logger.debug(f"RPC URL: {self.SOLANA_RPC_URL}")

# Create a global instance
try:
    config = Config()
except Exception as e:
    logger.critical(f"Kritischer Fehler beim Erstellen der Konfiguration: {e}")
    raise