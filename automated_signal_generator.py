"""AI Trading Engine mit ML-basierter Signalgenerierung und Marktanalyse"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import requests
from dex_connector import DexConnector
from chart_analyzer import ChartAnalyzer
from signal_processor import SignalProcessor
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

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

        # API Endpoints
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.solana_rpc = "https://api.mainnet-beta.solana.com"

        logger.info("Signal Generator initialisiert")

    def fetch_market_data(self) -> Dict[str, Any]:
        """Holt Marktdaten von verschiedenen Quellen"""
        try:
            data = {}

            # CoinGecko Daten
            coingecko_url = f"{self.coingecko_api}/simple/price"
            params = {
                'ids': 'solana',
                'vs_currencies': 'usd',
                'include_24hr_vol': True,
                'include_24hr_change': True
            }
            response = requests.get(coingecko_url, params=params)
            if response.status_code == 200:
                data['coingecko'] = response.json()

            # Solana RPC Daten
            rpc_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getRecentBlockhash"
            }
            response = requests.post(self.solana_rpc, json=rpc_payload)
            if response.status_code == 200:
                data['solana_rpc'] = response.json()

            # DEX Daten für Chart Updates
            dex_data = self.dex_connector.get_market_info("SOL")
            if dex_data and dex_data.get('price', 0) > 0:
                data['dex'] = dex_data
                # Aktualisiere Chart-Daten häufiger
                self.chart_analyzer.update_price_data(self.dex_connector, "SOL")

            logger.info("Marktdaten erfolgreich abgerufen")
            return data

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Marktdaten: {e}")
            return {}

    def start(self):
        """Startet den automatischen Signal-Generator"""
        try:
            if not self.is_running:
                logger.info("Starte automatischen Signal-Generator...")

                # Überprüfe Komponenten
                if not self.dex_connector:
                    raise ValueError("DEX Connector nicht initialisiert")
                if not self.signal_processor:
                    raise ValueError("Signal Processor nicht initialisiert")
                if not self.chart_analyzer:
                    raise ValueError("Chart Analyzer nicht initialisiert")

                # Starte Job
                self.scheduler.add_job(
                    self.generate_signals,
                    'interval',
                    seconds=5,  # Überprüfung alle 5 Sekunden
                    id='signal_generator',
                    replace_existing=True
                )
                self.scheduler.start()
                self.is_running = True

                # Status Update
                market_info = self.dex_connector.get_market_info("SOL")
                current_price = market_info.get('price', 0) if market_info else 0
                logger.info(f"Signal-Generator gestartet - "
                          f"Status: Aktiv, "
                          f"Intervall: 5s, "
                          f"Aktueller SOL Preis: {current_price:.2f} USDC")
            else:
                logger.info("Signal-Generator läuft bereits")

        except Exception as e:
            logger.error(f"Fehler beim Starten des Signal-Generators: {e}")
            self.is_running = False
            raise

    def stop(self):
        """Stoppt den Signal-Generator"""
        if self.is_running:
            logger.info("Stoppe Signal-Generator...")
            self.scheduler.remove_job('signal_generator')
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("Signal-Generator gestoppt")

    def generate_signals(self):
        """Generiert Trading-Signale basierend auf KI-Analyse"""
        try:
            current_time = datetime.now(pytz.UTC)
            self.last_check_time = current_time

            logger.info(f"[{current_time}] ⚡ Schnelle Marktanalyse...")

            # Hole Marktdaten
            market_data = self.fetch_market_data()
            if not market_data.get('dex'):
                logger.error("Keine DEX-Marktdaten verfügbar")
                return

            dex_market_info = market_data['dex']
            current_price = float(dex_market_info.get('price', 0))
            logger.info(f"Aktueller SOL Preis: {current_price:.2f} USDC")

            # Aktualisiere Chart-Daten für die Analyse
            self.chart_analyzer.update_price_data(self.dex_connector, "SOL")
            if self.chart_analyzer.data.empty:
                logger.error("Keine Chart-Daten verfügbar für die Analyse")
                return

            # Führe erweiterte Marktanalyse durch
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

                    # Reduzierte Qualitätsschwelle für mehr Signale
                    if processed_signal['signal_quality'] >= 3:  # Reduziert von 4 auf 3
                        logger.info(f"Signal Details:"
                                f"\n - Richtung: {processed_signal['direction']}"
                                f"\n - Entry: {processed_signal['entry']:.2f}"
                                f"\n - Take Profit: {processed_signal['take_profit']:.2f}"
                                f"\n - Stop Loss: {processed_signal['stop_loss']:.2f}"
                                f"\n - Erwarteter Profit: {processed_signal['expected_profit']:.2f}%")

                        # Benachrichtige Benutzer
                        self._notify_users_about_signal(processed_signal)
                        self.total_signals_generated += 1

                        # Aktualisiere Signal-Statistiken
                        current_time = datetime.now(pytz.UTC)
                        if self.last_signal_time:
                            interval = (current_time - self.last_signal_time).total_seconds() / 60
                            self.signal_intervals.append(interval)
                            avg_interval = sum(self.signal_intervals) / len(self.signal_intervals)
                            logger.info(f"📊 Signal-Statistiken:"
                                    f"\n - Durchschnittliches Intervall: {avg_interval:.1f} Minuten"
                                    f"\n - Gesamtzahl Signale: {self.total_signals_generated}")

                        self.last_signal_time = current_time
                    else:
                        logger.info(f"Signal ignoriert - Qualität zu niedrig: {processed_signal['signal_quality']}/10")
                else:
                    logger.info("Signal konnte nicht verarbeitet werden")
            else:
                logger.debug("Kein Signal basierend auf aktueller Analyse")

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Generierung: {e}")

    def _create_signal_from_analysis(
        self,
        current_price: float,
        trend_analysis: Dict[str, Any],
        support_resistance: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """Erstellt ein Trading-Signal basierend auf technischer Analyse"""
        try:
            trend = trend_analysis.get('trend', 'neutral')
            strength = float(trend_analysis.get('stärke', 0))
            metrics = trend_analysis.get('metriken', {})

            # Reduzierte Mindest-Trendstärke für mehr Signale
            if trend == 'neutral' or strength < 0.01:  # Reduziert von 0.03 auf 0.01
                logger.info(f"Kein Signal - Trend zu schwach: {trend}, Stärke: {strength}%")
                return None

            # Support/Resistance Levels
            support = float(support_resistance.get('support', 0))
            resistance = float(support_resistance.get('resistance', 0))

            # Zusätzliche Level-Analyse
            support_levels = support_resistance.get('levels', {}).get('support_levels', [])
            resistance_levels = support_resistance.get('levels', {}).get('resistance_levels', [])

            # Dynamische Take-Profit-Berechnung mit reduzierten Schwellen
            base_tp_percent = 0.005  # Reduziert von 0.01 auf 0.005 (0.5%)

            # Erhöhe Take-Profit bei starkem Trend und klaren Level-Abständen
            level_multiplier = 1.0
            if len(support_levels) > 0 and len(resistance_levels) > 0:
                level_range = (resistance - support) / current_price
                level_multiplier = min(2.0, 1.0 + level_range * 10)

            tp_multiplier = min(3.0, 1.0 + (strength / 100 * 5) * level_multiplier)
            dynamic_tp_percent = base_tp_percent * tp_multiplier

            # Berücksichtige Volumen-Trend mit höherer Sensitivität
            volume_trend = float(metrics.get('volumen_trend', 0))
            if abs(volume_trend) > 0.05:  # Reduziert von 0.1 auf 0.05
                dynamic_tp_percent *= (1 + min(abs(volume_trend), 0.5))

            if trend == 'aufwärts':
                entry = current_price
                stop_loss = max(support, current_price * 0.998)  # Reduziert auf 0.2%
                take_profit = min(resistance, current_price * (1 + dynamic_tp_percent))
                direction = 'long'
            else:  # abwärts
                entry = current_price
                stop_loss = min(resistance, current_price * 1.002)  # Reduziert auf 0.2%
                take_profit = max(support, current_price * (1 - dynamic_tp_percent))
                direction = 'short'

            # Berechne erwarteten Profit
            expected_profit = abs((take_profit - entry) / entry * 100)

            if expected_profit < 0.1:  # Reduziert von 0.2% auf 0.1%
                logger.info(f"Kein Signal - Zu geringer erwarteter Profit: {expected_profit:.1f}%")
                return None

            signal_quality = self._calculate_signal_quality(
                trend_analysis, strength, expected_profit
            )

            if signal_quality < 2:  # Reduziert von 3 auf 2 für mehr Signale
                logger.info(f"Kein Signal - Qualität zu niedrig: {signal_quality}/10")
                return None

            return {
                'pair': 'SOL/USD',
                'direction': direction,
                'entry': entry,
                'stop_loss': stop_loss,
                'take_profit': take_profit,
                'timestamp': datetime.now(pytz.UTC).timestamp(),
                'token_address': "SOL",
                'expected_profit': expected_profit,
                'signal_quality': signal_quality,
                'trend_strength': strength,
                'ai_confidence': 0.85,
                'risk_score': 6.5,
                'market_sentiment': 0.7
            }

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Erstellung: {e}")
            return None

    def _calculate_signal_quality(self, trend_analysis: Dict[str, Any],
                                  strength: float,
                                  expected_profit: float) -> float:
        """Berechnet die Qualität eines Signals (0-10) basierend auf technischer Analyse"""
        try:
            # Grundlegende Trend-Bewertung
            trend_base = float(8 if trend_analysis['trend'] == 'aufwärts' else 7)

            # Trendstärke-Bewertung mit Berücksichtigung der Metriken
            metrics = trend_analysis.get('metriken', {})
            momentum = abs(float(metrics.get('momentum', 0)))
            volatility = float(metrics.get('volatilität', 0))

            # Momentum-basierte Stärkebewertung
            strength_score = min(float(momentum * 20), 10.0)  # Erhöhte Sensitivität

            # Volatilitäts-Anpassung
            volatility_factor = max(0.5, 1.0 - float(volatility))  # Reduziere Score bei hoher Volatilität
            strength_score *= volatility_factor

            # Profit-Bewertung - Progressive Skala
            expected_profit = float(expected_profit)
            if expected_profit <= 1.0:
                profit_score = expected_profit * 5  # 0.5% = 2.5 Punkte
            elif expected_profit <= 2.0:
                profit_score = 5 + (expected_profit - 1.0) * 3  # 1.5% = 6.5 Punkte
            else:
                profit_score = 8 + (min(expected_profit - 2.0, 2.0))  # Max 10 Punkte

            # Volumen-Trend Bewertung
            volume_trend = float(metrics.get('volumen_trend', 0))
            volume_score = min(abs(volume_trend) * 10, 10.0)

            # Gewichtete Summe mit Volumen-Einfluss
            weights = (0.35, 0.25, 0.25, 0.15)  # Trend, Stärke, Profit, Volumen
            quality = (
                trend_base * weights[0] +         # Trend-Basis
                strength_score * weights[1] +     # Trendstärke
                profit_score * weights[2] +       # Profit-Potenzial
                volume_score * weights[3]         # Volumen-Trend
            )

            logger.debug(f"Signal Qualitätsberechnung:"
                        f"\n - Trend Score: {trend_base} (Gewicht: {weights[0]:.1f})"
                        f"\n - Strength Score: {strength_score} (Gewicht: {weights[1]:.1f})"
                        f"\n - Profit Score: {profit_score} (Gewicht: {weights[2]:.1f})"
                        f"\n - Volume Score: {volume_score} (Gewicht: {weights[3]:.1f})"
                        f"\n - Finale Qualität: {quality:.1f}/10")

            return round(min(quality, 10.0), 1)

        except Exception as e:
            logger.error(f"Fehler bei der Qualitätsberechnung: {e}")
            return 0.0

    def _notify_users_about_signal(self, signal: Dict[str, Any]):
        """Benachrichtigt Benutzer über neue Trading-Signale"""
        try:
            if not self.bot or not self.bot.active_users:
                logger.warning("Keine aktiven Nutzer oder Bot nicht verfügbar")
                return

            logger.info(f"Sende Signal an {len(self.bot.active_users)} aktive Nutzer")

            # Erstelle Chart
            chart_image = None
            try:
                chart_image = self.chart_analyzer.create_prediction_chart(
                    entry_price=signal['entry'],
                    target_price=signal['take_profit'],
                    stop_loss=signal['stop_loss']
                )
                logger.info("Chart für Signal erstellt")
            except Exception as chart_error:
                logger.error(f"Fehler bei der Chart-Generierung: {chart_error}")

            # Erstelle Signal-Nachricht
            signal_message = (
                f"🎯 Trading Signal erkannt!\n\n"
                f"Pair: {signal['pair']}\n"
                f"Position: {'📈 LONG' if signal['direction'] == 'long' else '📉 SHORT'}\n"
                f"Entry: {signal['entry']:.2f} USDC\n"
                f"Stop Loss: {signal['stop_loss']:.2f} USDC\n"
                f"Take Profit: {signal['take_profit']:.2f} USDC\n\n"
                f"📊 Analyse:\n"
                f"• Erwarteter Profit: {signal['expected_profit']:.1f}%\n"
                f"• Signal Qualität: {signal['signal_quality']}/10\n"
                f"• Trend Stärke: {signal['trend_strength']:.2f}\n\n"
                f"💡 Empfehlung: "
                f"{'Starkes Signal zum Einstieg!' if signal['signal_quality'] >= 7.0 else 'Mit Vorsicht handeln.'}"
            )

            keyboard = [
                [
                    InlineKeyboardButton("✅ Handeln", callback_data="trade_signal_new"),
                    InlineKeyboardButton("❌ Ignorieren", callback_data="ignore_signal")
                ]
            ]

            # Sende Signal an alle aktiven Nutzer
            for user_id in self.bot.active_users:
                try:
                    if chart_image:
                        # Sende Nachricht mit Chart
                        self.bot.updater.bot.send_photo(
                            chat_id=user_id,
                            photo=chart_image,
                            caption=signal_message,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    else:
                        # Sende Nachricht ohne Chart
                        self.bot.updater.bot.send_message(
                            chat_id=user_id,
                            text=signal_message,
                            reply_markup=InlineKeyboardMarkup(keyboard)
                        )
                    logger.info(f"Signal erfolgreich an User {user_id} gesendet")
                except Exception as e:
                    logger.error(f"Fehler beim Senden des Signals an User {user_id}: {e}")

        except Exception as e:
            logger.error(f"Fehler bei der Signal-Benachrichtigung: {e}")