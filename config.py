import os
from dataclasses import dataclass

@dataclass
class Config:
    # Telegram Config
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0'))

    # Solana Config
    SOLANA_NETWORK = os.getenv('SOLANA_NETWORK', 'mainnet-beta')
    SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')

    # Optional: Custom RPC URLs for different networks
    RPC_URLS = {
        'devnet': 'https://api.devnet.solana.com',
        'mainnet-beta': 'https://api.mainnet-beta.solana.com'
    }

    def __post_init__(self):
        # Ensure we're using the correct RPC URL for the selected network
        if not self.SOLANA_RPC_URL:
            self.SOLANA_RPC_URL = self.RPC_URLS.get(self.SOLANA_NETWORK, self.RPC_URLS['mainnet-beta'])