import os
from dataclasses import dataclass

@dataclass
class Config:
    # Telegram Config
    TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
    ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '0'))
    
    # Solana Config
    SOLANA_NETWORK = "mainnet-beta"
    SOLANA_RPC_URL = os.getenv('SOLANA_RPC_URL', 'https://api.mainnet-beta.solana.com')
    
    # DEX Config
    RAYDIUM_API_URL = "https://api.raydium.io/v2"
    
    # Trading Config
    MIN_TRADE_AMOUNT = 0.1  # SOL
    MAX_TRADE_AMOUNT = 100  # SOL
    SLIPPAGE_TOLERANCE = 0.5  # %

    # Messages
    WELCOME_MESSAGE = """
🚀 Willkommen beim Solana Trading Signal Bot!

Verfügbare Befehle:
/start - Bot starten
/hilfe - Zeigt diese Hilfe an
/wallet - Wallet-Verwaltung
/trade - Neuen Trade starten
/status - Aktueller Status
/chart - Chart Analysis
"""

    HELP_MESSAGE = """
📚 Verfügbare Befehle:

🔹 Basis Befehle:
/start - Bot starten
/hilfe - Diese Hilfe anzeigen
/status - Aktuellen Status anzeigen

🔹 Wallet Befehle:
/wallet - Wallet-Info anzeigen
/senden - SOL senden
/empfangen - Einzahlungsadresse anzeigen

🔹 Trading Befehle:
/trade - Neuen Trade starten
/chart - Chart Analysis
/position - Offene Positionen
/historie - Trade-Historie

⚠️ Bitte handeln Sie verantwortungsvoll!
"""
