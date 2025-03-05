import os
from dataclasses import dataclass

@dataclass
class Config:
    # Telegram Config
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0'))

    # Solana Config
    SOLANA_NETWORK = os.getenv('SOLANA_NETWORK', 'mainnet-beta')  # oder 'devnet' für Tests
    SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')