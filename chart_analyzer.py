import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class ChartAnalyzer:
    def __init__(self):
        self.data = pd.DataFrame()
        self.last_update = None
        self.min_data_points = 2  # Minimum für schnelle Signale
        self.last_support = None
        self.last_resistance = None

    def update_price_data(self, dex_connector, token_address: str):
        """Aktualisiert die Preisdaten"""
        try:
            current_time = datetime.now()

            # Überprüfe ob das letzte Update weniger als 3 Sekunden her ist
            if self.last_update and (current_time - self.last_update).total_seconds() < 3:
                return

            market_info = dex_connector.get_market_info(token_address)
            if market_info and market_info.get('price', 0) > 0:
                new_data = pd.DataFrame([{
                    'timestamp': current_time,
                    'price': float(market_info['price']),
                    'volume': float(market_info.get('volume', 0))
                }])

                self.data = pd.concat([self.data, new_data], ignore_index=True)
                self.data = self.data.drop_duplicates(subset=['timestamp'])
                self.data = self.data.sort_values('timestamp')

                # Behalte nur die letzten 30 Minuten für sehr schnelle Analyse
                cutoff_time = current_time - timedelta(minutes=30)
                self.data = self.data[self.data['timestamp'] > cutoff_time]

                self.last_update = current_time
                logger.info(f"Neue Preisdaten hinzugefügt - Aktueller Preis: {market_info['price']:.2f} USDC")

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

            # Bestimme Trend und Stärke - Maximale Sensitivität
            trend = 'aufwärts' if last_price > first_price else 'abwärts'
            strength = abs((last_price - first_price) / first_price * 100)  # Prozentuale Änderung

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

            prices = self.data['price'].values

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
            current_price = self.data['price'].iloc[-1]
            return {
                'support': current_price * 0.995,  # 0.5% unter aktuellem Preis
                'resistance': current_price * 1.005  # 0.5% über aktuellem Preis
            }

        return {'support': 0, 'resistance': 0}