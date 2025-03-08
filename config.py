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
            # Load Telegram configuration with better error handling
            self.TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
            if not self.TELEGRAM_TOKEN:
                logger.error("TELEGRAM_TOKEN nicht gefunden in Umgebungsvariablen")
                logger.debug(f"Verfügbare Umgebungsvariablen: {', '.join(list(os.environ.keys()))}")
            
            admin_id = os.environ.get('ADMIN_USER_ID', '0')
            logger.debug(f"Geladene ADMIN_USER_ID: {admin_id}")

            try:
                self.ADMIN_USER_ID = int(admin_id)
                logger.info(f"Admin ID konfiguriert: {self.ADMIN_USER_ID}")
            except ValueError:
                logger.error(f"Ungültige ADMIN_USER_ID: {admin_id}")
                raise ValueError("ADMIN_USER_ID muss eine gültige Zahl sein")
                
            # Load session secret
            self.SESSION_SECRET = os.environ.get('SESSION_SECRET')
            if not self.SESSION_SECRET:
                logger.warning("SESSION_SECRET nicht gefunden, generiere zufälligen Wert")
                import secrets
                self.SESSION_SECRET = secrets.token_hex(16)

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
            logger.warning("TELEGRAM_TOKEN nicht gesetzt - wird zur Laufzeit benötigt")
            
        if not self.ADMIN_USER_ID:
            logger.warning("ADMIN_USER_ID nicht gesetzt - wird zur Laufzeit benötigt")
            
        if not isinstance(self.ADMIN_USER_ID, int):
            raise ValueError("ADMIN_USER_ID muss eine Zahl sein")

        if self.TELEGRAM_TOKEN and len(self.TELEGRAM_TOKEN) < 20:
            logger.warning("TELEGRAM_TOKEN scheint zu kurz zu sein - prüfen Sie den Wert")

# Create a global instance
try:
    config = Config()
except Exception as e:
    logger.critical(f"Kritischer Fehler beim Erstellen der Konfiguration: {e}")
    config = None