import logging
from datetime import datetime
from typing import Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
from dex_connector import DexConnector
from chart_analyzer import ChartAnalyzer
from signal_processor import SignalProcessor

logger = logging.getLogger(__name__)

class AutomatedSignalGenerator:
    def __init__(self, dex_connector: DexConnector, signal_processor: SignalProcessor, bot):
        self.dex_connector = dex_connector
        self.signal_processor = signal_processor
        self.chart_analyzer = ChartAnalyzer()
        self.bot = bot
        self.scheduler = BackgroundScheduler(timezone=pytz.UTC)
        self.is_running = False

    def start(self):
        """Startet den automatischen Signal-Generator"""
        if not self.is_running:
            logger.info("Starte automatischen Signal-Generator...")
            self.scheduler.add_job(
                self.generate_signals,
                'interval',
                minutes=5,
                id='signal_generator'
            )
            self.scheduler.start()
            self.is_running = True
            logger.info("Signal-Generator läuft jetzt im Hintergrund")

    def stop(self):
        """Stoppt den Signal-Generator"""
        if self.is_running:
            self.scheduler.remove_job('signal_generator')
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Signal-Generator gestoppt")

    def generate_signals(self):
        """Generiert Trading-Signale basierend auf Marktanalyse"""
        try:
            logger.info("Analysiere Markt für neue Trading-Signale...")

            # Hole aktuelle Marktdaten
            market_info = self.dex_connector.get_market_info("SOL")
            if not market_info:
                logger.error("Keine Marktdaten verfügbar")
                return

            # Aktualisiere Chart-Daten
            self.chart_analyzer.update_price_data(self.dex_connector, "SOL")
            trend_analysis = self.chart_analyzer.analyze_trend()
            support_resistance = self.chart_analyzer.get_support_resistance()

            # Erstelle Signal basierend auf Analyse
            current_price = float(market_info.get('price', 0))
            signal = self._create_signal_from_analysis(
                current_price, trend_analysis, support_resistance
            )

            if signal:
                # Verarbeite und sende Signal
                processed_signal = self.signal_processor.process_signal(signal)
                if processed_signal:
                    self._notify_users_about_signal(processed_signal)
                    logger.info(f"Neues Trading-Signal generiert: {processed_signal['pair']}")

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Generierung: {e}")

    def _create_signal_from_analysis(
        self, current_price: float, 
        trend_analysis: Dict[str, Any],
        support_resistance: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Erstellt ein Trading-Signal basierend auf technischer Analyse"""
        try:
            # Bestimme Trend und Richtung
            trend = trend_analysis.get('trend', 'neutral')
            strength = trend_analysis.get('stärke', 0)

            if trend == 'neutral' or strength < 0.5:
                return None

            # Bestimme Entry, Stop Loss und Take Profit
            support = support_resistance.get('support', 0)
            resistance = support_resistance.get('resistance', 0)

            if trend == 'aufwärts':
                entry = current_price
                stop_loss = max(support, current_price * 0.95)  # 5% Stop Loss
                take_profit = min(resistance, current_price * 1.15)  # 15% Take Profit
                direction = 'long'
            else:
                entry = current_price
                stop_loss = min(resistance, current_price * 1.05)  # 5% Stop Loss
                take_profit = max(support, current_price * 0.85)  # 15% Take Profit
                direction = 'short'

            return {
                'pair': 'SOL/USD',
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(pytz.UTC).timestamp(),
                'dex_connector': self.dex_connector,
                'token_address': "SOL"
            }

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Erstellung: {e}")
            return None

    def _notify_users_about_signal(self, signal: Dict[str, Any]):
        """Benachrichtigt Benutzer über neue Trading-Signale"""
        try:
            signal_message = (
                f"🚨 Neues Trading Signal!\n\n"
                f"Pair: {signal['pair']}\n"
                f"Signal: {'📈 LONG' if signal['direction'] == 'long' else '📉 SHORT'}\n"
                f"Einstieg: {signal['entry']:.2f} USD\n"
                f"Stop Loss: {signal['stop_loss']:.2f} USD\n"
                f"Take Profit: {signal['take_profit']:.2f} USD\n\n"
                f"Erwarteter Profit: {signal['expected_profit']:.1f}%\n"
                f"Signal-Qualität: {signal['signal_quality']}/10\n\n"
                f"Nutzen Sie /signal um mehr Details zu sehen und das Signal zu handeln."
            )

            # Sende Nachricht an alle aktiven Bot-Benutzer
            # (Implementierung abhängig von der Bot-Struktur)
            if hasattr(self.bot, 'config') and hasattr(self.bot.config, 'ADMIN_USER_ID'):
                self.bot.updater.bot.send_message(
                    chat_id=self.bot.config.ADMIN_USER_ID,
                    text=signal_message
                )

        except Exception as e:
            logger.error(f"Fehler beim Senden der Signal-Benachrichtigung: {e}")