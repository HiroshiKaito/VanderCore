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
            # Chart-Analyse durchführen
            self.chart_analyzer.update_price_data(signal_data.get('dex_connector'), signal_data.get('token_address'))
            trend_analysis = self.chart_analyzer.analyze_trend()
            support_resistance = self.chart_analyzer.get_support_resistance()

            # Berechne erwartete Rendite
            entry_price = float(signal_data.get('entry', 0))
            target_price = float(signal_data.get('take_profit', 0))
            expected_profit_percent = ((target_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

            # Risikoanalyse
            risk_score, risk_recommendations = self.risk_analyzer.analyze_transaction_risk(
                float(signal_data.get('entry', 0)), []
            )

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
                'support': support_resistance.get('support', 0),
                'resistance': support_resistance.get('resistance', 0),
                'expected_profit': expected_profit_percent,
                'risk_score': risk_score,
                'risk_recommendations': risk_recommendations,
                'signal_quality': self._calculate_signal_quality(
                    trend_analysis, risk_score, expected_profit_percent
                )
            }

            # Filtere nur hochwertige Signale
            if processed_signal['signal_quality'] >= 7:
                self.active_signals.append(processed_signal)
                logger.info(f"Hochwertiges Signal verarbeitet: {processed_signal['pair']}")
                return processed_signal
            else:
                logger.info(f"Signal verworfen (niedrige Qualität): {processed_signal['pair']}")
                return {}

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

    def _calculate_signal_quality(self, trend_analysis: Dict[str, Any], 
                                risk_score: float, 
                                expected_profit: float) -> float:
        """Berechnet die Qualität eines Signals (0-10)"""
        try:
            # Gewichtete Faktoren für die Signalqualität
            trend_weight = 0.4
            risk_weight = 0.3
            profit_weight = 0.3

            # Trend-Score (0-10)
            trend_score = 8 if trend_analysis['trend'] == 'aufwärts' else 3
            trend_score *= min(trend_analysis['stärke'] / 5, 1)  # Stärke-Faktor

            # Risiko-Score (0-10, invertiert da niedriges Risiko besser ist)
            risk_score = (1 - risk_score) * 10

            # Profit-Score (0-10, basierend auf erwartetem Profit)
            profit_score = min(expected_profit / 5, 10)  # 50% Profit = Maximalscore

            # Gewichtete Summe der Scores
            final_score = (
                trend_score * trend_weight +
                risk_score * risk_weight +
                profit_score * profit_weight
            )

            return round(final_score, 1)

        except Exception as e:
            logger.error(f"Fehler bei der Signalqualitätsberechnung: {e}")
            return 0.0