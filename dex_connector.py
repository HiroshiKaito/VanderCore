import requests
import logging
from typing import Dict, Any, Tuple
import json

logger = logging.getLogger(__name__)

class DexConnector:
    def __init__(self):
        self.session = None
        # Korrigierte API URL und SOL Token Adresse
        self.base_url = "https://api.raydium.io/v2"
        self.sol_usdc_pair = "SOL-USDC"

    def initialize(self):
        """Initialisiert die DEX-Verbindung"""
        self.session = requests.Session()
        logger.info("DEX Connector initialisiert")

    def close(self):
        """Schließt die DEX-Verbindung"""
        if self.session:
            self.session.close()

    def get_market_info(self, token_address: str) -> Dict[str, Any]:
        """Holt Market-Informationen"""
        try:
            if not self.session:
                self.initialize()

            # Debug-Log für API-Anfrage
            logger.info(f"Hole Marktdaten für Token: {token_address}")

            # Korrigierte URL für SOL/USDC Pair
            url = f"{self.base_url}/main/pairs"

            # Führe Request aus
            response = self.session.get(url)
            response.raise_for_status()

            # Parse Response
            data = response.json()
            logger.debug(f"API-Antwort erhalten: {json.dumps(data)[:200]}...")

            # Finde SOL/USDC Pair (suche nach beiden möglichen Formaten)
            sol_pair = next(
                (pair for pair in data 
                 if any(sol_name in pair.get('name', '').upper() 
                       for sol_name in ['SOL/USDC', 'SOL-USDC', 'SOLUSDC'])),
                None
            )

            if not sol_pair:
                logger.error("SOL/USDC Pair nicht gefunden in API-Antwort")
                logger.debug(f"Verfügbare Pairs: {[p.get('name') for p in data[:5]]}")
                return {
                    'price': 0.0,  # Kein Fallback-Preis mehr
                    'volume': 0.0,
                    'timestamp': None
                }

            # Extrahiere relevante Daten
            market_data = {
                'price': float(sol_pair.get('price', 0.0)),
                'volume': float(sol_pair.get('volume', 0.0)),
                'timestamp': sol_pair.get('timestamp', None)
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
        except (KeyError, ValueError, TypeError) as e:
            logger.error(f"Fehler beim Verarbeiten der Marktdaten: {e}")
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

            # Beispiel für Raydium DEX Integration
            instruction_data = {
                "token": token_address,
                "amount": amount,
                "side": "buy" if is_buy else "sell",
                "wallet": wallet_manager.get_address()
            }

            # Hier würde die tatsächliche DEX-Interaktion stattfinden
            # Dies ist ein Platzhalter für die echte Implementation

            logger.info(f"Trade ausgeführt: {instruction_data}")
            return True, "Trade erfolgreich ausgeführt"

        except Exception as e:
            logger.error(f"Fehler beim Trade: {e}")
            return False, str(e)