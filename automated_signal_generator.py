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
        self.last_signal_time = None
        self.signal_intervals = []  # Speichert die Zeitintervalle zwischen Signalen

    def start(self):
        """Startet den automatischen Signal-Generator"""
        if not self.is_running:
            logger.info("Starte automatischen Signal-Generator...")
            self.scheduler.add_job(
                self.generate_signals,
                'interval',
                seconds=15,  # Auf 15 Sekunden reduziert für noch schnellere Reaktion
                id='signal_generator'
            )
            self.scheduler.start()
            self.is_running = True
            logger.info("Signal-Generator läuft jetzt im Hintergrund - Überprüfung alle 15 Sekunden")

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

            # Berechne Zeit seit letztem Signal
            if self.last_signal_time:
                time_since_last = (current_time - self.last_signal_time).total_seconds() / 60  # in Minuten
                logger.info(f"Zeit seit letztem Signal: {time_since_last:.1f} Minuten")

            logger.info(f"[{current_time}] ⚡ Schnelle Marktanalyse...")

            # Hole aktuelle Marktdaten
            market_info = self.dex_connector.get_market_info("SOL")
            if not market_info or market_info.get('price', 0) == 0:
                logger.error("Keine Marktdaten verfügbar oder ungültiger Preis")
                return

            current_price = float(market_info.get('price', 0))
            logger.info(f"Aktueller SOL Preis: {current_price:.2f} USDC")

            # Aktualisiere Chart-Daten
            self.chart_analyzer.update_price_data(self.dex_connector, "SOL")
            trend_analysis = self.chart_analyzer.analyze_trend()
            support_resistance = self.chart_analyzer.get_support_resistance()

            # Detaillierte Marktanalyse Logs
            logger.info(f"Marktanalyse - Trend: {trend_analysis.get('trend')}, "
                       f"Stärke: {trend_analysis.get('stärke', 0):.2f}")
            logger.info(f"Support/Resistance - Support: {support_resistance.get('support', 0):.2f}, "
                       f"Resistance: {support_resistance.get('resistance', 0):.2f}")

            # Erstelle Signal basierend auf Analyse
            signal = self._create_signal_from_analysis(
                current_price, trend_analysis, support_resistance
            )

            if signal:
                # Verarbeite und sende Signal
                processed_signal = self.signal_processor.process_signal(signal)
                if processed_signal:
                    logger.info(f"Signal erstellt - Qualität: {processed_signal['signal_quality']}/10")
                    if processed_signal['signal_quality'] >= 4:  # Reduziert von 5 auf 4
                        logger.info(f"Signal Details:"
                                  f"\n - Richtung: {processed_signal['direction']}"
                                  f"\n - Entry: {processed_signal['entry']:.2f}"
                                  f"\n - Take Profit: {processed_signal['take_profit']:.2f}"
                                  f"\n - Stop Loss: {processed_signal['stop_loss']:.2f}"
                                  f"\n - Erwarteter Profit: {processed_signal['expected_profit']:.2f}%")
                        self._notify_users_about_signal(processed_signal)
                        self.total_signals_generated += 1

                        # Aktualisiere Signal-Statistiken
                        current_time = datetime.now(pytz.UTC)
                        if self.last_signal_time:
                            interval = (current_time - self.last_signal_time).total_seconds() / 60
                            self.signal_intervals.append(interval)
                            avg_interval = sum(self.signal_intervals) / len(self.signal_intervals)
                            logger.info(f"🚨 Trading-Signal gesendet: {processed_signal['pair']}")
                            logger.info(f"📊 Signal-Statistiken:"
                                      f"\n - Durchschnittliches Intervall: {avg_interval:.1f} Minuten"
                                      f"\n - Gesamtzahl Signale: {self.total_signals_generated}")

                        self.last_signal_time = current_time
                    else:
                        logger.info(f"Signal ignoriert - Qualität zu niedrig: {processed_signal['signal_quality']}/10")
                else:
                    logger.info("Signal konnte nicht verarbeitet werden")
            else:
                logger.info("Kein Signal basierend auf aktueller Analyse")

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Generierung: {e}")

    def _create_signal_from_analysis(
        self, current_price: float, 
        trend_analysis: Dict[str, Any],
        support_resistance: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Erstellt ein Trading-Signal basierend auf technischer Analyse"""
        try:
            trend = trend_analysis.get('trend', 'neutral')
            strength = trend_analysis.get('stärke', 0)

            if trend == 'neutral' or strength < 0.05:  # Reduziert auf 0.05% für mehr Signale
                logger.info(f"Kein Signal - Trend zu schwach: {trend}, Stärke: {strength}%")
                return None

            # Bestimme Entry, Stop Loss und Take Profit
            support = support_resistance.get('support', 0)
            resistance = support_resistance.get('resistance', 0)

            # Dynamische Take-Profit-Berechnung basierend auf Trendstärke
            base_tp_percent = 0.015  # 1.5% Basis Take-Profit
            # Erhöhe Take-Profit bei stärkerem Trend
            tp_multiplier = min(3.0, 1.0 + (strength / 100) * 10)  # Max 3x Basis-TP
            dynamic_tp_percent = base_tp_percent * tp_multiplier

            if trend == 'aufwärts':
                entry = current_price
                stop_loss = max(support, current_price * 0.995)  # 0.5% Stop Loss
                # Berechne dynamisches Take-Profit, maximal bis zum Resistance-Level
                take_profit = min(resistance, current_price * (1 + dynamic_tp_percent))
                direction = 'long'
            else:  # abwärts
                entry = current_price
                stop_loss = min(resistance, current_price * 1.005)  # 0.5% Stop Loss
                # Berechne dynamisches Take-Profit, maximal bis zum Support-Level
                take_profit = max(support, current_price * (1 - dynamic_tp_percent))
                direction = 'short'

            # Berechne erwarteten Profit
            expected_profit = abs((take_profit - entry) / entry * 100)

            if expected_profit < 0.3:  # Reduziert auf 0.3% für mehr Signale
                logger.info(f"Kein Signal - Zu geringer erwarteter Profit: {expected_profit:.1f}%")
                return None

            signal_quality = self._calculate_signal_quality(trend_analysis, strength, expected_profit)
            if signal_quality < 3:  # Reduziert auf 3 für mehr Signale
                logger.info(f"Kein Signal - Qualität zu niedrig: {signal_quality}/10")
                return None

            logger.info(f"Neues Signal erstellt:"
                       f"\n - Trend: {trend}"
                       f"\n - Trendstärke: {strength:.2f}%"
                       f"\n - Take-Profit-Multiplikator: {tp_multiplier:.1f}x"
                       f"\n - Erwarteter Profit: {expected_profit:.1f}%"
                       f"\n - Signalqualität: {signal_quality}/10")

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
                'signal_quality': signal_quality,
                'trend_strength': strength
            }

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Erstellung: {e}")
            return None

    def _calculate_signal_quality(self, trend_analysis: Dict[str, Any], strength: float, expected_profit: float) -> float:
        """Berechnet die Qualität eines Signals (0-10) - Optimierte Version"""
        try:
            # Grundlegende Trend-Bewertung
            trend_base = 8 if trend_analysis['trend'] == 'aufwärts' else 7

            # Trendstärke-Bewertung
            strength_score = min(strength * 30, 10)  # Erhöhte Sensitivität

            # Profit-Bewertung - Progressive Skala
            if expected_profit <= 1.0:
                profit_score = expected_profit * 5  # 0.5% = 2.5 Punkte
            elif expected_profit <= 2.0:
                profit_score = 5 + (expected_profit - 1.0) * 3  # 1.5% = 6.5 Punkte
            else:
                profit_score = 8 + (min(expected_profit - 2.0, 2.0))  # Max 10 Punkte

            # Dynamische Gewichtung basierend auf Marktsituation
            if strength > 0.2:  # Starker Trend
                weights = (0.2, 0.5, 0.3)  # Mehr Gewicht auf Trendstärke
            elif expected_profit > 1.5:  # Hoher potenzieller Profit
                weights = (0.3, 0.3, 0.4)  # Mehr Gewicht auf Profit
            else:
                weights = (0.3, 0.4, 0.3)  # Ausgewogene Gewichtung

            # Gewichtete Summe
            quality = (
                trend_base * weights[0] +  # Trend-Basis
                strength_score * weights[1] +  # Trendstärke
                profit_score * weights[2]  # Profit-Potenzial
            )

            # Bonus für besonders starke Signale
            if strength > 0.3 and expected_profit > 2.0:
                quality *= 1.1  # 10% Bonus

            logger.debug(f"Signal Qualitätsberechnung:"
                        f"\n - Trend Score: {trend_base} (Gewicht: {weights[0]:.1f})"
                        f"\n - Strength Score: {strength_score} (Gewicht: {weights[1]:.1f})"
                        f"\n - Profit Score: {profit_score} (Gewicht: {weights[2]:.1f})"
                        f"\n - Finale Qualität: {quality:.1f}/10")

            return round(min(quality, 10), 1)

        except Exception as e:
            logger.error(f"Fehler bei der Qualitätsberechnung: {e}")
            return 0.0

    def _notify_users_about_signal(self, signal: Dict[str, Any]):
        """Benachrichtigt Benutzer über neue Trading-Signale"""
        try:
            # Hole das aktuelle Wallet-Guthaben
            balance = self.bot.wallet_manager.get_balance()

            # Erstelle Prediction Chart
            logger.info("Erstelle Prediction Chart für Trading Signal...")
            chart_image = None
            try:
                chart_image = self.chart_analyzer.create_prediction_chart(
                    entry_price=signal['entry'],
                    target_price=signal['take_profit'],
                    stop_loss=signal['stop_loss']
                )
            except Exception as chart_error:
                logger.error(f"Fehler bei der Chart-Generierung: {chart_error}")
                # Fahre mit der Signal-Nachricht fort, auch wenn das Chart fehlschlägt

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

            # Sende Nachricht mit Chart an alle aktiven Bot-Benutzer
            if hasattr(self.bot, 'config') and hasattr(self.bot.config, 'ADMIN_USER_ID'):
                try:
                    # Sende zuerst das Chart-Bild
                    if chart_image:
                        logger.info("Sende Prediction Chart...")
                        self.bot.updater.bot.send_photo(
                            chat_id=self.bot.config.ADMIN_USER_ID,
                            photo=chart_image,
                            caption="📊 Preisprognose für das Trading Signal"
                        )
                        logger.info("Prediction Chart erfolgreich gesendet")
                    else:
                        logger.warning("Kein Chart-Bild verfügbar für das Signal")

                    # Dann sende die Signal-Details
                    logger.info("Sende Signal-Details...")
                    self.bot.updater.bot.send_message(
                        chat_id=self.bot.config.ADMIN_USER_ID,
                        text=signal_message,
                        reply_markup={"inline_keyboard": keyboard}
                    )
                    logger.info("Trading Signal erfolgreich gesendet")

                except Exception as send_error:
                    logger.error(f"Fehler beim Senden der Nachrichten: {send_error}")
                    # Versuche es erneut nur mit der Text-Nachricht
                    try:
                        self.bot.updater.bot.send_message(
                            chat_id=self.bot.config.ADMIN_USER_ID,
                            text=signal_message + "\n\n⚠️ Chart konnte nicht generiert werden.",
                            reply_markup={"inline_keyboard": keyboard}
                        )
                    except Exception as fallback_error:
                        logger.error(f"Auch Fallback-Nachricht fehlgeschlagen: {fallback_error}")

        except Exception as e:
            logger.error(f"Fehler beim Senden der Signal-Benachrichtigung: {e}")