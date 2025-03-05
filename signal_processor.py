from typing import Dict, Any, List
import logging
from datetime import datetime
from chart_analyzer import ChartAnalyzer
from risk_analyzer import RiskAnalyzer
from ai_trading_engine import AITradingEngine

logger = logging.getLogger(__name__)

class SignalProcessor:
    def __init__(self):
        self.active_signals: List[Dict[str, Any]] = []
        self.chart_analyzer = ChartAnalyzer()
        self.risk_analyzer = RiskAnalyzer()
        self.ai_engine = AITradingEngine()  # Neue KI-Engine

    def process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """Verarbeitet ein eingehendes Trading Signal mit KI-Unterstützung"""
        try:
            # Chart-Analyse durchführen
            self.chart_analyzer.update_price_data(signal_data.get('dex_connector'), signal_data.get('token_address'))
            trend_analysis = self.chart_analyzer.analyze_trend()
            support_resistance = self.chart_analyzer.get_support_resistance()

            # KI-Vorhersage abrufen
            ai_prediction = self.ai_engine.predict_next_move(
                self.chart_analyzer.data
            )

            # Berechne erwartete Rendite basierend auf KI-Vorhersage
            entry_price = float(signal_data.get('entry', 0))
            predicted_price = ai_prediction.get('prediction', entry_price)
            expected_profit_percent = ((predicted_price - entry_price) / entry_price) * 100 if entry_price > 0 else 0

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
                'ai_confidence': ai_prediction.get('confidence', 0),
                'predicted_price': predicted_price,
                'signal_quality': self._calculate_signal_quality(
                    trend_analysis, 
                    risk_score, 
                    expected_profit_percent,
                    ai_prediction.get('confidence', 0)
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

    def get_executed_signals(self) -> List[Dict[str, Any]]:
        """Gibt alle ausgeführten Signale zurück"""
        return [signal for signal in self.active_signals if signal['status'] == 'ausgeführt']

    def mark_signal_executed(self, signal_id: int):
        """Markiert ein Signal als ausgeführt"""
        if 0 <= signal_id < len(self.active_signals):
            self.active_signals[signal_id]['status'] = 'ausgeführt'

    def _calculate_signal_quality(self, trend_analysis: Dict[str, Any], 
                               risk_score: float, 
                               expected_profit: float,
                               ai_confidence: float) -> float:
        """Berechnet die Qualität eines Signals (0-10) mit KI-Einfluss"""
        try:
            # Grundlegende Trend-Bewertung
            trend_base = 8 if trend_analysis['trend'] == 'aufwärts' else 7

            # Trendstärke-Bewertung
            strength_score = min(trend_analysis['stärke'] * 30, 10)  # Erhöhte Sensitivität

            # Profit-Bewertung - Progressive Skala
            if expected_profit <= 1.0:
                profit_score = expected_profit * 5  # 0.5% = 2.5 Punkte
            elif expected_profit <= 2.0:
                profit_score = 5 + (expected_profit - 1.0) * 3  # 1.5% = 6.5 Punkte
            else:
                profit_score = 8 + (min(expected_profit - 2.0, 2.0))  # Max 10 Punkte

            # KI-Konfidenz-Score
            ai_score = ai_confidence * 10  # Konvertiere 0-1 zu 0-10

            # Dynamische Gewichtung basierend auf KI-Konfidenz
            if ai_confidence > 0.8:  # Hohe KI-Konfidenz
                weights = (0.2, 0.2, 0.3, 0.3)  # Mehr Gewicht auf KI und Profit
            elif ai_confidence > 0.6:  # Mittlere KI-Konfidenz
                weights = (0.25, 0.25, 0.25, 0.25)  # Ausgewogene Gewichtung
            else:  # Niedrige KI-Konfidenz
                weights = (0.3, 0.3, 0.3, 0.1)  # Weniger Gewicht auf KI

            # Gewichtete Summe
            quality = (
                trend_base * weights[0] +          # Trend-Basis
                strength_score * weights[1] +      # Trendstärke
                profit_score * weights[2] +        # Profit-Potenzial
                ai_score * weights[3]              # KI-Konfidenz
            )

            # Bonus für besonders starke Signale mit hoher KI-Konfidenz
            if ai_confidence > 0.8 and expected_profit > 2.0:
                quality *= 1.1  # 10% Bonus

            logger.debug(f"Signal Qualitätsberechnung:"
                        f"\n - Trend Score: {trend_base:.1f} (Gewicht: {weights[0]:.1f})"
                        f"\n - Strength Score: {strength_score:.1f} (Gewicht: {weights[1]:.1f})"
                        f"\n - Profit Score: {profit_score:.1f} (Gewicht: {weights[2]:.1f})"
                        f"\n - AI Score: {ai_score:.1f} (Gewicht: {weights[3]:.1f})"
                        f"\n - Finale Qualität: {quality:.1f}/10")

            return round(min(quality, 10), 1)

        except Exception as e:
            logger.error(f"Fehler bei der Signalqualitätsberechnung: {e}")
            return 0.0