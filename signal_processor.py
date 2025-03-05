from typing import Dict, Any, List
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

class SignalProcessor:
    def __init__(self):
        self.active_signals: List[Dict[str, Any]] = []
        
    def process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet ein eingehendes Trading Signal"""
        try:
            processed_signal = {
                'timestamp': datetime.now().timestamp(),
                'pair': signal_data.get('pair', ''),
                'direction': signal_data.get('direction', ''),
                'entry': float(signal_data.get('entry', 0)),
                'stop_loss': float(signal_data.get('stop_loss', 0)),
                'take_profit': float(signal_data.get('take_profit', 0)),
                'status': 'neu'
            }
            
            self.active_signals.append(processed_signal)
            return processed_signal
            
        except Exception as e:
            logger.error(f"Fehler bei der Signal-Verarbeitung: {e}")
            return {}
            
    def validate_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Überprüft ob ein Signal gültig ist"""
        required_fields = ['pair', 'direction', 'entry', 'stop_loss', 'take_profit']
        return all(field in signal_data for field in required_fields)
        
    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Gibt alle aktiven Signale zurück"""
        return [signal for signal in self.active_signals if signal['status'] == 'neu']
        
    def mark_signal_executed(self, signal_id: int):
        """Markiert ein Signal als ausgeführt"""
        if 0 <= signal_id < len(self.active_signals):
            self.active_signals[signal_id]['status'] = 'ausgeführt'
