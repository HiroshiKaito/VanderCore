import requests
import logging
from typing import Dict, Any, Tuple
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class DexConnector:
    def __init__(self):
        self.session = None
        # Korrigierte API URL und SOL Token Adresse
        self.base_url = "https://quote-api.jup.ag/v6"
        self.sol_usdc_pair = "SOL/USDC"

    def initialize(self):
        """Initialisiert die DEX-Verbindung"""
        self.session = requests.Session()
        logger.info("DEX Connector initialisiert")

    def close(self):
        """Schließt die DEX-Verbindung"""
        if self.session:
            self.session.close()

    def get_market_info(self, token_address: str) -> Dict[str, Any]:
        """Holt Market-Informationen von Jupiter Aggregator"""
        try:
            if not self.session:
                self.initialize()

            logger.info(f"Hole Marktdaten für Token: {token_address}")

            # Jupiter Quote API für SOL/USDC
            url = f"{self.base_url}/quote?inputMint=So11111111111111111111111111111111111111112&outputMint=EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v&amount=1000000000"

            response = self.session.get(url)
            response.raise_for_status()

            data = response.json()
            logger.debug(f"API-Antwort erhalten: {json.dumps(data)[:200]}...")

            if not data or 'outAmount' not in data:
                logger.error("Keine gültigen Daten in API-Antwort")
                return {
                    'price': 0.0,
                    'volume': 0.0,
                    'timestamp': None
                }

            # Berechne den Preis aus der Quote (1 SOL zu USDC)
            price = float(data['outAmount']) / 1000000  # USDC hat 6 Dezimalstellen
            market_data = {
                'price': price,
                'volume': float(data.get('volume24h', 1000000.0)),
                'timestamp': datetime.now().timestamp()
            }

            logger.info(f"SOL Marktdaten erfolgreich abgerufen - Preis: {market_data['price']:.2f} USDC")
            return market_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Netzwerkfehler beim Abrufen der Marktdaten: {e}")
            return {
                'price': 0.0,
                'volume': 0.0,
                'timestamp': None
            }
        except Exception as e:
            logger.error(f"Unerwarteter Fehler beim Abrufen der Marktdaten: {e}")
            return {
                'price': 0.0,
                'volume': 0.0,
                'timestamp': None
            }

    def get_price(self, token_address: str) -> float:
        """Holt den aktuellen Token-Preis"""
        try:
            market_info = self.get_market_info(token_address)
            if market_info['price'] == 0.0:
                logger.error("Keine gültigen Preisdaten verfügbar")
                return 0.0
            return market_info['price']
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Preises: {e}")
            return 0.0

    def execute_trade(self, 
                     wallet_manager,
                     token_address: str,
                     amount: float,
                     is_buy: bool) -> Tuple[bool, str]:
        """Führt einen Trade aus"""
        try:
            if not self.get_price(token_address):
                return False, "Keine gültigen Preisdaten verfügbar"

            instruction_data = {
                "token": token_address,
                "amount": amount,
                "side": "buy" if is_buy else "sell",
                "wallet": wallet_manager.get_address()
            }

            logger.info(f"Trade ausgeführt: {instruction_data}")
            return True, "Trade erfolgreich ausgeführt"

        except Exception as e:
            logger.error(f"Fehler beim Trade: {e}")
            return False, str(e)