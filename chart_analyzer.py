import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple
import logging
from datetime import datetime, timedelta
import mplfinance as mpf
import io

logger = logging.getLogger(__name__)

class ChartAnalyzer:
    def __init__(self):
        self.data = pd.DataFrame()
        self.last_update = None
        self.min_data_points = 2
        self.last_support = None
        self.last_resistance = None

        # Chart Styling
        self.style = mpf.make_mpf_style(
            base_mpf_style='charles',
            gridstyle='',
            y_on_right=True,
            marketcolors=mpf.make_marketcolors(
                up='green',
                down='red',
                edge='inherit',
                wick='inherit',
                volume='in'
            )
        )

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

            # Aktualisiere Daten für Plotly Chart
            new_data = pd.DataFrame({
                'open': [price],
                'high': [price * 1.001],  # Simulierte Werte für OHLC
                'low': [price * 0.999],
                'close': [price],
                'volume': [volume],
                'timestamp': [current_time]
            })

            if self.data.empty:
                self.data = new_data
            else:
                self.data = pd.concat([self.data, new_data])

            # Behalte nur die letzten 30 Minuten
            cutoff_time = current_time - timedelta(minutes=30)
            self.data = self.data[self.data['timestamp'] > cutoff_time]

            logger.info(f"Preisdaten erfolgreich aktualisiert - {len(self.data)} Datenpunkte")

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Preisdaten: {e}")

    def analyze_trend(self) -> Dict[str, Any]:
        """Analysiert den aktuellen Trend mit erweiterten Metriken"""
        try:
            if len(self.data) < self.min_data_points:
                logger.info(f"Zu wenig Daten für Trendanalyse (benötigt: {self.min_data_points})")
                return {'trend': 'neutral', 'stärke': 0}

            # Berechne verschiedene Trend-Indikatoren
            closes = self.data['close'].values
            volumes = self.data['volume'].values

            # Trendstärke basierend auf Preisbewegung
            price_change = (closes[-1] - closes[0]) / closes[0]
            price_volatility = np.std(closes) / np.mean(closes)

            # Volumen-Analyse
            volume_trend = (volumes[-1] - volumes[0]) / volumes[0]
            volume_consistency = np.std(volumes) / np.mean(volumes)

            # Momentum-Berechnung
            momentum = price_change * (1 + volume_trend)

            # Bestimme Trend und Stärke
            if abs(price_change) < 0.001:  # 0.1% Schwelle
                trend = 'neutral'
                strength = 0
            else:
                trend = 'aufwärts' if price_change > 0 else 'abwärts'
                # Normalisierte Stärke (0-1)
                base_strength = min(abs(momentum) * 10, 1)  # Basis-Stärke
                volume_factor = 1 - min(volume_consistency, 0.5)  # Volumen-Konsistenz
                strength = base_strength * volume_factor

            trend_data = {
                'trend': trend,
                'stärke': strength,
                'metriken': {
                    'preis_änderung': price_change,
                    'volumen_trend': volume_trend,
                    'volatilität': price_volatility,
                    'momentum': momentum
                }
            }

            logger.info(f"Trendanalyse: {trend}, Stärke: {strength:.2f}")
            return trend_data

        except Exception as e:
            logger.error(f"Fehler bei der Trendanalyse: {e}")
            return {'trend': 'neutral', 'stärke': 0}

    def get_support_resistance(self) -> Dict[str, float]:
        """Berechnet Support und Resistance Levels mit Clustering"""
        try:
            if len(self.data) < self.min_data_points * 2:
                logger.info(f"Zu wenig Daten für Support/Resistance Berechnung")
                return self._get_fallback_levels()

            # Sammle Preispunkte für Clustering
            price_points = np.concatenate([
                self.data['high'].values,
                self.data['low'].values
            ])

            # Identifiziere Preiscluster
            hist, bin_edges = np.histogram(price_points, bins='auto')
            peak_indices = np.where(hist >= np.mean(hist))[0]

            if len(peak_indices) < 2:
                logger.info("Nicht genug Preiscluster gefunden")
                return self._get_fallback_levels()

            # Berechne Support/Resistance aus Clustern
            levels = bin_edges[peak_indices]
            current_price = self.data['close'].iloc[-1]

            support_levels = levels[levels < current_price]
            resistance_levels = levels[levels > current_price]

            if len(support_levels) == 0 or len(resistance_levels) == 0:
                return self._get_fallback_levels()

            support = np.max(support_levels)
            resistance = np.min(resistance_levels)

            # Überprüfe ob die Levels signifikant sind
            price_range = (resistance - support) / support
            if price_range < 0.001:
                logger.info("Support/Resistance Levels zu eng beieinander")
                return self._get_fallback_levels()

            # Aktualisiere die letzten gültigen Levels
            self.last_support = support
            self.last_resistance = resistance

            logger.info(f"Support/Resistance berechnet - Support: {support:.2f}, Resistance: {resistance:.2f}")

            return {
                'support': support,
                'resistance': resistance,
                'levels': {
                    'support_levels': support_levels.tolist(),
                    'resistance_levels': resistance_levels.tolist()
                }
            }

        except Exception as e:
            logger.error(f"Fehler bei der Support/Resistance Berechnung: {e}")
            return self._get_fallback_levels()

    def create_prediction_chart(self, entry_price: float, target_price: float, stop_loss: float) -> Optional[bytes]:
        """Erstellt einen Chart mit Preisprognose und Markierungen"""
        try:
            if self.data.empty:
                logger.error("Keine Daten für Chart-Erstellung verfügbar")
                return None

            # Bereite Daten vor
            df = self.data.copy()
            df.set_index('timestamp', inplace=True)

            # Erstelle Annotations für Entry, Target und Stoploss
            annotations = [
                dict(y=entry_price, text='Entry'),
                dict(y=target_price, text='Target'),
                dict(y=stop_loss, text='Stop')
            ]

            # Erstelle Chart
            buffer = io.BytesIO()
            mpf.plot(
                df,
                type='candle',
                style=self.style,
                volume=True,
                title='Preisprognose mit Levels',
                ylabel='Preis (USDC)',
                ylabel_lower='Volumen',
                hlines=dict(
                    hlines=[entry_price, target_price, stop_loss],
                    colors=['blue', 'green', 'red'],
                    linestyle='--'
                ),
                savefig=buffer
            )

            logger.info("Trading Chart erfolgreich erstellt")
            return buffer.getvalue()

        except Exception as e:
            logger.error(f"Fehler bei der Chart-Erstellung: {e}")
            return None

    def _get_fallback_levels(self) -> Dict[str, float]:
        """Liefert Fallback-Werte für Support/Resistance"""
        if self.last_support and self.last_resistance:
            return {
                'support': self.last_support,
                'resistance': self.last_resistance
            }

        if len(self.data) > 0:
            current_price = self.data['close'].iloc[-1]
            return {
                'support': current_price * 0.995,
                'resistance': current_price * 1.005
            }

        return {'support': 0, 'resistance': 0}