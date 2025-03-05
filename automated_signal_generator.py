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
        self.last_check_time = None
        self.total_signals_generated = 0

    def start(self):
        """Startet den automatischen Signal-Generator"""
        if not self.is_running:
            logger.info("Starte automatischen Signal-Generator...")
            self.scheduler.add_job(
                self.generate_signals,
                'interval',
                minutes=1,  # Auf 1 Minute reduziert für schnellere Reaktion
                id='signal_generator'
            )
            self.scheduler.start()
            self.is_running = True
            logger.info("Signal-Generator läuft jetzt im Hintergrund - Überprüfung alle 60 Sekunden")

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
            current_time = datetime.now(pytz.UTC)
            self.last_check_time = current_time

            logger.info(f"[{current_time}] ⚡ Schnelle Marktanalyse...")

            # Hole aktuelle Marktdaten mit hoher Priorität
            market_info = self.dex_connector.get_market_info("SOL")
            if not market_info:
                logger.error("Keine Marktdaten verfügbar")
                return

            # Aktualisiere Chart-Daten
            self.chart_analyzer.update_price_data(self.dex_connector, "SOL")
            trend_analysis = self.chart_analyzer.analyze_trend()
            support_resistance = self.chart_analyzer.get_support_resistance()

            logger.info(f"Marktanalyse - Trend: {trend_analysis.get('trend')}, "
                       f"Stärke: {trend_analysis.get('stärke', 0):.2f}")

            # Erstelle Signal basierend auf Analyse
            current_price = float(market_info.get('price', 0))
            signal = self._create_signal_from_analysis(
                current_price, trend_analysis, support_resistance
            )

            if signal:
                # Verarbeite und sende Signal mit hoher Priorität
                processed_signal = self.signal_processor.process_signal(signal)
                if processed_signal:
                    self._notify_users_about_signal(processed_signal)
                    self.total_signals_generated += 1
                    logger.info(f"🚨 Trading-Signal generiert: {processed_signal['pair']}, "
                              f"Qualität: {processed_signal['signal_quality']}/10")

            logger.info(f"Schnellanalyse abgeschlossen. Signals: {self.total_signals_generated}")

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

            # Berechne erwarteten Profit und Signal-Qualität
            expected_profit = abs((take_profit - entry) / entry * 100)
            signal_quality = self._calculate_signal_quality(trend_analysis, strength, expected_profit)

            return {
                'pair': 'SOL/USD',
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(pytz.UTC).timestamp(),
                'dex_connector': self.dex_connector,
                'token_address': "SOL",
                'expected_profit': expected_profit,
                'signal_quality': signal_quality
            }

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Erstellung: {e}")
            return None

    def _calculate_signal_quality(self, trend_analysis: Dict[str, Any], strength: float, expected_profit: float) -> float:
        """Berechnet die Qualität eines Signals (0-10)"""
        try:
            # Gewichte verschiedene Faktoren
            trend_score = 8 if trend_analysis['trend'] == 'aufwärts' else 6
            strength_score = min(strength * 10, 10)
            profit_score = min(expected_profit / 3, 10)  # 30% Profit = max Score

            # Gewichtete Summe
            quality = (trend_score * 0.4 + strength_score * 0.3 + profit_score * 0.3)

            return round(quality, 1)

        except Exception as e:
            logger.error(f"Fehler bei der Qualitätsberechnung: {e}")
            return 7.0  # Standardwert

    def _notify_users_about_signal(self, signal: Dict[str, Any]):
        """Benachrichtigt Benutzer über neue Trading-Signale"""
        try:
            # Hole das aktuelle Wallet-Guthaben
            balance = self.bot.wallet_manager.get_balance()

            signal_message = (
                f"⚡ SCHNELLES TRADING SIGNAL!\n\n"
                f"Pair: {signal['pair']}\n"
                f"Signal: {'📈 LONG' if signal['direction'] == 'long' else '📉 SHORT'}\n"
                f"Einstieg: {signal['entry']:.2f} USD\n"
                f"Stop Loss: {signal['stop_loss']:.2f} USD\n"
                f"Take Profit: {signal['take_profit']:.2f} USD\n\n"
                f"Erwarteter Profit: {signal['expected_profit']:.1f}%\n"
                f"Signal-Qualität: {signal['signal_quality']}/10\n\n"
                f"💰 Verfügbares Guthaben: {balance:.4f} SOL\n\n"
                f"Schnell reagieren! Der Markt wartet nicht! 🚀"
            )

            # Erstelle Inline-Buttons für die Benutzerinteraktion
            keyboard = [
                [
                    {"text": "✅ Handeln", "callback_data": "trade_signal_new"},
                    {"text": "❌ Ignorieren", "callback_data": "ignore_signal"}
                ]
            ]

            # Sende Nachricht an alle aktiven Bot-Benutzer
            if hasattr(self.bot, 'config') and hasattr(self.bot.config, 'ADMIN_USER_ID'):
                self.bot.updater.bot.send_message(
                    chat_id=self.bot.config.ADMIN_USER_ID,
                    text=signal_message,
                    reply_markup={"inline_keyboard": keyboard}
                )

        except Exception as e:
            logger.error(f"Fehler beim Senden der Signal-Benachrichtigung: {e}")