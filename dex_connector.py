import requests
import logging
from typing import Dict, Any, Tuple
import json
from datetime import datetime

logger = logging.getLogger(__name__)

class DexConnector:
    def __init__(self):
        self.session = None
        # Jupiter API URL und SOL Token Adresse
        self.base_url = "https://quote-api.jup.ag/v6"
        self.sol_usdc_pair = "SOL/USDC"
        self.sol_token = "So11111111111111111111111111111111111111112"  # Native SOL Token
        self.usdc_token = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"  # USDC Token

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
            quote_url = f"{self.base_url}/quote"
            params = {
                "inputMint": self.sol_token,
                "outputMint": self.usdc_token,
                "amount": 1000000000  # 1 SOL in Lamports
            }

            response = self.session.get(quote_url, params=params)
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

    def execute_trade(self, 
                     wallet_manager,
                     token_address: str,
                     amount: float,
                     is_buy: bool) -> Tuple[bool, str]:
        """Führt einen Trade auf Jupiter DEX aus"""
        try:
            # 1. Hole aktuelle Marktdaten und Quote
            quote_url = f"{self.base_url}/quote"
            params = {
                "inputMint": self.sol_token if is_buy else self.usdc_token,
                "outputMint": self.usdc_token if is_buy else self.sol_token,
                "amount": int(amount * (1e9 if is_buy else 1e6))  # Konvertiere zu Lamports oder USDC Decimals
            }

            quote_response = self.session.get(quote_url, params=params)
            quote_response.raise_for_status()
            quote_data = quote_response.json()

            # 2. Erstelle die Transaktion
            tx_url = f"{self.base_url}/swap"
            tx_data = {
                "quoteResponse": quote_data,
                "userPublicKey": wallet_manager.get_address(),
                "wrapUnwrapSOL": True
            }

            tx_response = self.session.post(tx_url, json=tx_data)
            tx_response.raise_for_status()
            tx_result = tx_response.json()

            # 3. Signiere und sende die Transaktion
            signed_tx = wallet_manager.sign_transaction(tx_result['swapTransaction'])
            tx_hash = wallet_manager.send_transaction(signed_tx)

            logger.info(f"Trade erfolgreich ausgeführt - Hash: {tx_hash}")
            return True, f"Trade erfolgreich - Transaktion: {tx_hash}"

        except Exception as e:
            logger.error(f"Fehler beim Trade: {e}")
            return False, str(e)

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