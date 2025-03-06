import pandas as pd
import numpy as np
from typing import Dict, Any
import logging
from datetime import datetime, timedelta

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

            # Aktualisiere Daten für Plotly Chart
            new_data = pd.DataFrame({
                'price': [price],
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
        """Analysiert den aktuellen Trend"""
        try:
            if len(self.data) < self.min_data_points:
                logger.info(f"Zu wenig Daten für Trendanalyse (benötigt: {self.min_data_points})")
                return {'trend': 'neutral', 'stärke': 0}

            # Sortiere nach Zeitstempel und hole die letzten Datenpunkte
            recent_data = self.data.sort_values('timestamp').tail(2)

            # Berechne den Trend basierend auf der direkten Preisänderung
            first_price = recent_data['price'].iloc[0]
            last_price = recent_data['price'].iloc[-1]

            # Bestimme Trend und Stärke
            trend = 'aufwärts' if last_price > first_price else 'abwärts'
            strength = abs((last_price - first_price) / first_price * 100)

            # Reduziere die Mindest-Trendstärke für Signale
            min_strength = 0.05  # Reduziert für höhere Sensitivität
            if strength < min_strength:
                trend = 'neutral'
                strength = 0

            logger.info(f"Trendanalyse: {trend}, Stärke: {strength:.2f}%")

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

            prices = self.data['price'].values

            # Berechne Support und Resistance mit engen Perzentilen
            support = np.percentile(prices, 30)
            resistance = np.percentile(prices, 70)

            # Überprüfe ob die Levels signifikant sind
            price_range = (resistance - support) / support
            if price_range < 0.001:
                logger.info(f"Support/Resistance Levels zu eng beieinander")
                return self._get_fallback_levels()

            # Aktualisiere die letzten gültigen Levels
            self.last_support = support
            self.last_resistance = resistance

            logger.info(f"Support/Resistance berechnet - Support: {support:.2f}, Resistance: {resistance:.2f}")

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

        if len(self.data) > 0:
            current_price = self.data['price'].iloc[-1]
            return {
                'support': current_price * 0.995,
                'resistance': current_price * 1.005
            }

        return {'support': 0, 'resistance': 0}