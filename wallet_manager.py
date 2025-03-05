import logging
from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.system_program import TransferParams, transfer
from solana.transaction import Transaction
from base58 import b58encode, b58decode
import qrcode
from io import BytesIO
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

class WalletManager:
    def __init__(self, rpc_url: str):
        """Initialisiert den Wallet Manager mit echter Solana-Verbindung"""
        self.client = Client(rpc_url)
        self.keypair = None
        logger.info("WalletManager mit Solana-Verbindung initialisiert")

    def create_wallet(self) -> tuple[str, str]:
        """Erstellt eine neue Solana Wallet"""
        try:
            logger.info("Erstelle neue Solana-Wallet...")
            self.keypair = Keypair()
            public_key = str(self.keypair.public_key)
            # Private Key in Base58 Format für einfachere Handhabung
            private_key = b58encode(bytes(self.keypair.secret_key)).decode('ascii')
            logger.info(f"Neue Solana-Wallet erstellt mit Adresse: {public_key[:8]}...")
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
                return 0.0
            response = self.client.get_balance(self.keypair.public_key)
            if 'result' in response and 'value' in response['result']:
                # Konvertiere Lamports zu SOL (1 SOL = 1e9 Lamports)
                return float(response['result']['value']) / 1e9
            return 0.0
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Guthabens: {e}")
            return 0.0

    async def send_sol(self, to_address: str, amount: float) -> tuple[bool, str]:
        """Sendet SOL an eine andere Adresse"""
        try:
            if not self.keypair:
                return False, "Keine Wallet geladen"

            # Konvertiere SOL zu Lamports
            lamports = int(amount * 1e9)

            # Erstelle die Transaktion
            transfer_params = TransferParams(
                from_pubkey=self.keypair.public_key,
                to_pubkey=to_address,
                lamports=lamports
            )

            transaction = Transaction().add(transfer(transfer_params))

            # Sende die Transaktion
            result = await self.client.send_transaction(
                transaction,
                self.keypair
            )

            if 'result' in result:
                logger.info(f"Transaktion erfolgreich: {result['result'][:8]}...")
                return True, result['result']
            return False, "Transaktion fehlgeschlagen"

        except Exception as e:
            logger.error(f"Fehler bei der Transaktion: {e}")
            return False, str(e)

    def get_address(self) -> str:
        """Gibt die Wallet-Adresse zurück"""
        return str(self.keypair.public_key) if self.keypair else ""

    def generate_qr_code(self) -> BytesIO:
        """Generiert einen QR-Code für die Wallet-Adresse"""
        try:
            address = self.get_address()
            if not address:
                raise ValueError("Keine Wallet-Adresse verfügbar")

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(address)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            bio = BytesIO()
            img.save(bio, format='PNG')
            bio.seek(0)
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