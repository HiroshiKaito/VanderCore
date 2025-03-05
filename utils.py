import logging
from datetime import datetime
from typing import Dict, Any

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def format_amount(amount: float, decimals: int = 4) -> str:
    """Formatiert einen Betrag mit der angegebenen Anzahl von Dezimalstellen"""
    return f"{amount:.{decimals}f}"

def validate_amount(amount: str) -> tuple[bool, float]:
    """Überprüft ob ein eingegebener Betrag gültig ist"""
    try:
        amount = float(amount)
        if amount <= 0:
            return False, 0
        return True, amount
    except ValueError:
        return False, 0

def create_trade_message(trade_data: Dict[str, Any]) -> str:
    """Erstellt eine formatierte Nachricht für einen Trade"""
    return f"""
🔔 Neues Trading Signal

Pair: {trade_data['pair']}
Signal: {'📈 LONG' if trade_data['direction'] == 'long' else '📉 SHORT'}
Einstieg: {format_amount(trade_data['entry'])} SOL
Stop Loss: {format_amount(trade_data['stop_loss'])} SOL
Take Profit: {format_amount(trade_data['take_profit'])} SOL

⏰ {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
"""

def format_wallet_info(balance: float, address: str) -> str:
    """Erstellt eine formatierte Nachricht für Wallet-Informationen"""
    return f"""
💰 Wallet Information

Adresse: {address[:8]}...{address[-8:]}
Guthaben: {format_amount(balance)} SOL

⏰ Aktualisiert: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}
"""
