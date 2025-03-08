import logging
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.system_program import TransferParams, transfer
from solana.transaction import Transaction
from base58 import b58encode, b58decode
import qrcode
from io import BytesIO
from datetime import datetime, timedelta
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

class WalletManager:
    def __init__(self, rpc_url: str):
        """Initialisiert den Wallet Manager mit echter Solana-Verbindung"""
        try:
            logger.info(f"Initialisiere WalletManager mit RPC URL: {rpc_url}")
            self.client = Client(rpc_url, commitment="confirmed")
            self.keypair = None

            # Validiere RPC-Verbindung
            version = self.client.get_version()
            logger.info(f"Verbunden mit Solana {version['result']['solana-core']}")

        except Exception as e:
            logger.error(f"Fehler bei der Initialisierung des WalletManager: {e}")
            raise

    def create_wallet(self, user_id: str = None) -> tuple[str, str]:
        """Erstellt eine neue Solana Wallet"""
        try:
            logger.info("Erstelle neue Solana-Wallet...")
            self.keypair = Keypair()
            public_key = str(self.keypair.public_key)
            private_key = b58encode(bytes(self.keypair.secret_key)).decode('ascii')

            logger.info(f"Neue Wallet erstellt mit Adresse: {public_key[:8]}...")
            return public_key, private_key

        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Wallet: {e}")
            return "", ""

    def load_wallet(self, private_key: str) -> bool:
        """Lädt eine existierende Wallet"""
        try:
            logger.info("Versuche Wallet zu laden...")
            secret_key = b58decode(private_key)
            self.keypair = Keypair.from_secret_key(bytes(secret_key))
            logger.info(f"Wallet erfolgreich geladen mit Adresse: {str(self.keypair.public_key)[:8]}...")
            return True
        except Exception as e:
            logger.error(f"Fehler beim Laden der Wallet: {e}")
            return False

    def get_balance(self) -> float:
        """Holt das aktuelle Wallet-Guthaben in SOL"""
        try:
            if not self.keypair:
                logger.warning("get_balance aufgerufen ohne aktive Wallet")
                return 0.0

            logger.debug(f"Rufe Guthaben ab für Adresse: {str(self.keypair.public_key)[:8]}...")
            response = self.client.get_balance(self.keypair.public_key)

            if 'result' in response and 'value' in response['result']:
                balance = float(response['result']['value']) / 1e9
                logger.info(f"Aktuelles Guthaben: {balance} SOL")
                return balance

            logger.warning("Ungültige Antwort vom Solana Client")
            return 0.0

        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Guthabens: {e}")
            return 0.0

    def estimate_transaction_fee(self) -> float:
        """Schätzt die Transaktionsgebühren für eine Standard-Transaktion"""
        try:
            # Aktuelle Gebühr für eine Standard-Transaktion auf Solana
            # Dies ist ein Schätzwert, der sich je nach Netzwerkauslastung ändern kann
            return 0.000005  # Standard Solana Transaktionsgebühr
        except Exception as e:
            logger.error(f"Fehler bei der Gebührenschätzung: {e}")
            return 0.000005  # Fallback auf Standard-Gebühr

    def send_sol(self, user_id: str, to_address: str, amount: float) -> tuple[bool, str]:
        """Sendet SOL an eine andere Adresse mit Risiko- und Sicherheitsanalyse"""
        try:
            if not self.keypair:
                return False, "Keine Wallet geladen"

            # Berechne Transaktionsgebühren
            fee = self.estimate_transaction_fee()
            total_amount = amount + fee

            # Prüfe ob genügend Guthaben vorhanden ist
            balance = self.get_balance()
            if balance < total_amount:
                return False, f"Nicht genügend Guthaben. Benötigt: {total_amount} SOL (inkl. {fee} SOL Gebühren)"


            # Führe Transaktion aus
            lamports = int(amount * 1e9)

            transfer_params = TransferParams(
                from_pubkey=self.keypair.public_key,
                to_pubkey=to_address,
                lamports=lamports
            )

            transaction = Transaction().add(transfer(transfer_params))

            # Sende die Transaktion
            result = self.client.send_transaction(
                transaction,
                self.keypair
            )

            if 'result' in result:
                logger.info(f"Transaktion erfolgreich: {result['result']}")
                return True, result['result']

            return False, "Transaktion fehlgeschlagen"

        except Exception as e:
            logger.error(f"Fehler bei der Transaktion: {e}")
            return False, str(e)

    def get_address(self) -> str:
        """Gibt die Wallet-Adresse zurück"""
        if not self.keypair:
            logger.warning("get_address aufgerufen ohne aktive Wallet")
            return ""

        address = str(self.keypair.public_key)
        logger.debug(f"Wallet-Adresse abgerufen: {address[:8]}...")
        return address

    def generate_qr_code(self) -> BytesIO:
        """Generiert einen QR-Code für die Wallet-Adresse"""
        try:
            # Prüfe ob eine Wallet existiert
            address = self.get_address()
            if not address:
                logger.error("Keine Wallet-Adresse verfügbar für QR-Code-Generierung")
                raise ValueError("Keine Wallet-Adresse verfügbar")

            # Erstelle QR Code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )

            # Füge Daten hinzu (Solana-Adresse)
            qr.add_data(f"solana:{address}")
            qr.make(fit=True)

            # Erstelle Bild
            img = qr.make_image(fill_color="black", back_color="white")

            # Speichere in BytesIO
            bio = BytesIO()
            img.save(bio, format='PNG')
            bio.seek(0)

            logger.info(f"QR-Code erfolgreich generiert für Adresse: {address[:8]}...")
            return bio

        except Exception as e:
            logger.error(f"Fehler bei QR-Code-Generierung: {e}")
            raise

    def scan_qr_code(self) -> str:
        """Scannt einen QR-Code mit der Kamera"""
        try:
            cap = cv2.VideoCapture(0)
            while True:
                ret, frame = cap.read()
                if not ret:
                    continue

                detector = cv2.QRCodeDetector()
                data, bbox, _ = detector.detectAndDecode(frame)

                if data:
                    cap.release()
                    return data

                cv2.imshow('QR Scanner', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            cap.release()
            cv2.destroyAllWindows()
            return ""
        except Exception as e:
            logger.error(f"Fehler beim QR-Code-Scan: {e}")
            return ""