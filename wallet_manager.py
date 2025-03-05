from solana.rpc.api import Client
from solana.keypair import Keypair
from solana.system_program import TransferParams, transfer
from solana.transaction import Transaction
from base58 import b58encode, b58decode
import os
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

class WalletManager:
    def __init__(self, rpc_url: str):
        self.client = Client(rpc_url)
        self.keypair = None
        
    def create_wallet(self) -> Tuple[str, str]:
        """Erstellt eine neue Solana Wallet"""
        self.keypair = Keypair()
        public_key = str(self.keypair.public_key)
        private_key = b58encode(self.keypair.secret_key).decode('ascii')
        return public_key, private_key
    
    def load_wallet(self, private_key: str):
        """Lädt eine existierende Wallet"""
        secret_key = b58decode(private_key)
        self.keypair = Keypair.from_secret_key(secret_key)
        
    def get_balance(self) -> float:
        """Holt das aktuelle Wallet-Guthaben"""
        try:
            balance = self.client.get_balance(self.keypair.public_key)
            return float(balance['result']['value']) / 1e9  # Convert lamports to SOL
        except Exception as e:
            logger.error(f"Fehler beim Abrufen des Guthabens: {e}")
            return 0.0
            
    async def send_transaction(self, to_pubkey: str, amount: float) -> Tuple[bool, str]:
        """Sendet eine Transaktion"""
        try:
            amount_lamports = int(amount * 1e9)  # Convert SOL to lamports
            
            transfer_params = TransferParams(
                from_pubkey=self.keypair.public_key,
                to_pubkey=to_pubkey,
                lamports=amount_lamports
            )
            
            transaction = Transaction().add(transfer(transfer_params))
            
            # Sende Transaktion
            result = await self.client.send_transaction(
                transaction,
                self.keypair
            )
            
            if 'result' in result:
                return True, result['result']
            return False, "Transaktion fehlgeschlagen"
            
        except Exception as e:
            logger.error(f"Fehler bei der Transaktion: {e}")
            return False, str(e)
            
    def get_address(self) -> str:
        """Gibt die Wallet-Adresse zurück"""
        return str(self.keypair.public_key) if self.keypair else ""
