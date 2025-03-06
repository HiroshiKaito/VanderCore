import pandas as pd
import numpy as np
from typing import Dict, Any
import logging
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import mplfinance as mpf
from io import BytesIO

logger = logging.getLogger(__name__)

class ChartAnalyzer:
    def __init__(self):
        self.data = pd.DataFrame()
        self.last_update = None
        self.min_data_points = 2
        self.last_support = None
        self.last_resistance = None

    def update_price_data(self, dex_connector, token_address: str):
        """Aktualisiert die Preisdaten"""
        try:
            current_time = datetime.now()
            logger.info(f"Starte Preisdaten-Update für {token_address}")

            # Überprüfe ob das letzte Update weniger als 3 Sekunden her ist
            if self.last_update and (current_time - self.last_update).total_seconds() < 3:
                logger.debug("Zu früh für neues Update, überspringe")
                return

            market_info = dex_connector.get_market_info(token_address)
            if not market_info or market_info.get('price', 0) <= 0:
                logger.error("Ungültige Marktdaten erhalten")
                return

            price = float(market_info['price'])
            volume = float(market_info.get('volume', 0))
            logger.info(f"Neue Marktdaten empfangen - Preis: {price:.2f} USDC, Volumen: {volume:.2f}")

            # Erstelle OHLC Daten für Candlestick Chart
            new_data = pd.DataFrame({
                'Open': [price],
                'High': [price * 1.002],  # Erhöhte Schwankung für bessere Visualisierung
                'Low': [price * 0.998],
                'Close': [price],
                'Volume': [volume]
            }, index=[current_time])  # Setze den Index direkt beim Erstellen

            logger.debug(f"Neue Daten erstellt:\n{new_data}")

            if self.data.empty:
                self.data = new_data
                logger.debug("Erste Daten gesetzt")
            else:
                self.data = pd.concat([self.data, new_data])
                logger.debug("Daten hinzugefügt")

            # Entferne Duplikate und sortiere
            self.data = self.data[~self.data.index.duplicated(keep='last')]
            self.data.sort_index(inplace=True)

            # Behalte nur die letzten 30 Minuten für sehr schnelle Analyse
            cutoff_time = current_time - timedelta(minutes=30)
            self.data = self.data[self.data.index > cutoff_time]

            logger.info(f"Preisdaten erfolgreich aktualisiert - {len(self.data)} Datenpunkte")
            logger.debug(f"Aktualisierte Daten:\n{self.data}")

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Preisdaten: {e}")

    def create_prediction_chart(self, entry_price: float, target_price: float, stop_loss: float) -> BytesIO:
        """Erstellt einen Candlestick-Chart mit Vorhersage und Ein-/Ausstiegspunkten"""
        try:
            logger.info(f"Starte Chart-Erstellung - Entry: {entry_price:.2f}, Target: {target_price:.2f}, Stop: {stop_loss:.2f}")

            if self.data.empty:
                logger.error("Keine Daten für Chart-Erstellung verfügbar")
                return None

            # Validiere Datenformat
            required_columns = ['Open', 'High', 'Low', 'Close', 'Volume']
            if not all(col in self.data.columns for col in required_columns):
                logger.error(f"Fehlende Spalten in den Daten. Verfügbar: {self.data.columns.tolist()}")
                return None

            # Überprüfe Index-Format
            if not isinstance(self.data.index, pd.DatetimeIndex):
                logger.error(f"Falsches Index-Format: {type(self.data.index)}")
                return None

            logger.debug(f"Chart-Daten vorm Plot:\n{self.data}")

            # Plot Style
            mc = mpf.make_marketcolors(
                up='#00ff00',      # Hellgrün für steigende Kerzen
                down='#ff0000',    # Hellrot für fallende Kerzen
                edge='inherit',
                wick='inherit',
                volume='#7B1FA2'   # Lila für Volumen
            )
            s = mpf.make_mpf_style(
                marketcolors=mc,
                gridstyle='solid',
                gridcolor='#444444',
                figcolor='#1a1a1a',
                facecolor='#2d2d2d',
                edgecolor='#444444'
            )

            try:
                # Plot erstellen
                fig, axlist = mpf.plot(
                    self.data,
                    type='candle',
                    volume=True,
                    style=s,
                    figsize=(12, 8),
                    title='\nSOL/USDC Preisprognose',
                    returnfig=True
                )
                logger.info("Grundlegender Chart erstellt")

                # Füge Entry, Target und Stop Loss Linien hinzu
                ax = axlist[0]
                ax.axhline(y=entry_price, color='lime', linestyle='--', label='Entry')
                ax.axhline(y=target_price, color='cyan', linestyle='--', label='Target')
                ax.axhline(y=stop_loss, color='red', linestyle='--', label='Stop')
                ax.legend()
                logger.info("Preislinien hinzugefügt")

                # Speichere Chart als PNG
                img_bio = BytesIO()
                fig.savefig(img_bio, format='png', dpi=100, bbox_inches='tight',
                           facecolor='#1a1a1a', edgecolor='none')
                img_bio.seek(0)
                plt.close(fig)

                logger.info("Chart erfolgreich als Bild gespeichert")
                return img_bio

            except Exception as plot_error:
                logger.error(f"Fehler beim Erstellen des Plots: {plot_error}")
                return None

        except Exception as e:
            logger.error(f"Fehler bei der Chart-Erstellung: {e}")
            return None

    def analyze_trend(self) -> Dict[str, Any]:
        """Analysiert den aktuellen Trend"""
        try:
            if len(self.data) < self.min_data_points:
                logger.info(f"Zu wenig Daten für Trendanalyse (benötigt: {self.min_data_points})")
                return {'trend': 'neutral', 'stärke': 0}

            # Sortiere nach Zeitstempel und hole die letzten Datenpunkte
            recent_data = self.data.sort_values('timestamp').tail(2)

            # Berechne den Trend basierend auf der direkten Preisänderung
            first_price = recent_data['Close'].iloc[0]
            last_price = recent_data['Close'].iloc[-1]

            # Bestimme Trend und Stärke - Maximale Sensitivität
            trend = 'aufwärts' if last_price > first_price else 'abwärts'
            strength = abs((last_price - first_price) / first_price * 100)  # Prozentuale Änderung

            # Reduziere die Mindest-Trendstärke für Signale
            min_strength = 0.05  # Reduziert von 0.1% auf 0.05% für höhere Sensitivität
            if strength < min_strength:
                trend = 'neutral'
                strength = 0

            logger.info(f"Trendanalyse: {trend}, Stärke: {strength:.2f}%, "
                       f"Von: {first_price:.2f} USDC -> Zu: {last_price:.2f} USDC")

            return {
                'trend': trend,
                'stärke': strength,
                'letzer_preis': last_price
            }

        except Exception as e:
            logger.error(f"Fehler bei der Trendanalyse: {e}")
            return {'trend': 'neutral', 'stärke': 0}

    def get_support_resistance(self) -> Dict[str, float]:
        """Berechnet Support und Resistance Levels"""
        try:
            if len(self.data) < self.min_data_points * 2:
                logger.info(f"Zu wenig Daten für Support/Resistance Berechnung")
                return self._get_fallback_levels()

            prices = self.data['Close'].values

            # Berechne Support und Resistance mit sehr engen Perzentilen
            support = np.percentile(prices, 30)  # Verringert von 40 auf 30
            resistance = np.percentile(prices, 70)  # Erhöht von 60 auf 70

            # Überprüfe ob die Levels signifikant sind
            price_range = (resistance - support) / support
            if price_range < 0.001:  # Reduziert von 0.002 auf 0.001 für sehr enge Ranges
                logger.info(f"Support/Resistance Levels zu eng beieinander (Range: {price_range:.2%})")
                return self._get_fallback_levels()

            # Aktualisiere die letzten gültigen Levels
            self.last_support = support
            self.last_resistance = resistance

            logger.info(f"Support/Resistance berechnet - Support: {support:.2f} USDC, "
                       f"Resistance: {resistance:.2f} USDC, Range: {price_range:.2%}")

            return {
                'support': support,
                'resistance': resistance
            }

        except Exception as e:
            logger.error(f"Fehler bei der Support/Resistance Berechnung: {e}")
            return self._get_fallback_levels()

    def _get_fallback_levels(self) -> Dict[str, float]:
        """Liefert Fallback-Werte für Support/Resistance"""
        if self.last_support and self.last_resistance:
            return {
                'support': self.last_support,
                'resistance': self.last_resistance
            }

        # Wenn keine vorherigen Levels existieren, berechne aus aktuellem Preis
        if len(self.data) > 0:
            current_price = self.data['Close'].iloc[-1]
            return {
                'support': current_price * 0.995,  # 0.5% unter aktuellem Preis
                'resistance': current_price * 1.005  # 0.5% über aktuellem Preis
            }

        return {'support': 0, 'resistance': 0}