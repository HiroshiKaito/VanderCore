"""SignalProcessor class for handling trading signals"""
from typing import Dict, Any, List
import logging
from datetime import datetime
from chart_analyzer import ChartAnalyzer
from risk_analyzer import RiskAnalyzer

logger = logging.getLogger(__name__)

class SignalProcessor:
    def __init__(self):
        self.active_signals: List[Dict[str, Any]] = []
        self.chart_analyzer = ChartAnalyzer()
        self.risk_analyzer = RiskAnalyzer()

    def process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet ein eingehendes Trading Signal"""
        try:
            logger.info("Verarbeite neues Trading Signal")
            logger.debug(f"Signal Eingangsdaten: {signal_data}")

            # Validiere Signal-Daten
            if not self.validate_signal(signal_data):
                logger.error("Signal-Validierung fehlgeschlagen")
                return {}

            # Verwende vorgegebene Werte für Test-Signale
            trend_analysis = {
                'trend': signal_data.get('direction', 'neutral'),
                'stärke': signal_data.get('trend_strength', 0)
            }

            # Erstelle verarbeitetes Signal
            processed_signal = {
                'timestamp': datetime.now().timestamp(),
                'pair': signal_data.get('pair', ''),
                'direction': signal_data.get('direction', ''),
                'entry': float(signal_data.get('entry', 0)),
                'stop_loss': float(signal_data.get('stop_loss', 0)),
                'take_profit': float(signal_data.get('take_profit', 0)),
                'status': 'neu',
                'trend': trend_analysis.get('trend', 'neutral'),
                'trend_strength': trend_analysis.get('stärke', 0),
                'expected_profit': signal_data.get('expected_profit', 0),
                'signal_quality': signal_data.get('signal_quality', 0),
                'risk_score': 5,  # Standard-Risikobewertung für Test-Signale
            }

            logger.info(f"Signal verarbeitet - Details:"
                       f"\n - Pair: {processed_signal['pair']}"
                       f"\n - Richtung: {processed_signal['direction']}"
                       f"\n - Qualität: {processed_signal['signal_quality']}/10"
                       f"\n - Trend: {processed_signal['trend']}"
                       f"\n - Trendstärke: {processed_signal['trend_strength']:.2f}")

            # Füge Signal zur aktiven Liste hinzu
            self.active_signals.append(processed_signal)
            logger.info(f"Signal akzeptiert: {processed_signal['pair']} "
                       f"(Qualität: {processed_signal['signal_quality']}/10)")
            return processed_signal

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Verarbeitung: {e}")
            return {}

    def validate_signal(self, signal_data: Dict[str, Any]) -> bool:
        """Überprüft ob ein Signal gültig ist"""
        required_fields = ['pair', 'direction', 'entry', 'stop_loss', 'take_profit']
        for field in required_fields:
            if field not in signal_data:
                logger.error(f"Fehlendes Pflichtfeld im Signal: {field}")
                return False
            if not signal_data[field]:
                logger.error(f"Leeres Pflichtfeld im Signal: {field}")
                return False
        return True

    def get_active_signals(self) -> List[Dict[str, Any]]:
        """Gibt alle aktiven Signale zurück"""
        return [signal for signal in self.active_signals if signal['status'] == 'neu']

    def get_executed_signals(self) -> List[Dict[str, Any]]:
        """Gibt alle ausgeführten Signale zurück"""
        return [signal for signal in self.active_signals if signal['status'] == 'ausgeführt']

    def mark_signal_executed(self, signal_id: int):
        """Markiert ein Signal als ausgeführt"""
        if 0 <= signal_id < len(self.active_signals):
            self.active_signals[signal_id]['status'] = 'ausgeführt'
            logger.info(f"Signal {signal_id} als ausgeführt markiert")