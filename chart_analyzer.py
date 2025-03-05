import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)

class ChartAnalyzer:
    def __init__(self):
        self.data = pd.DataFrame()

    def update_price_data(self, dex_connector, token_address: str):
        """Aktualisiert die Preisdaten"""
        try:
            market_info = dex_connector.get_market_info(token_address)
            # Verarbeite die Marktdaten
            if market_info and market_info.get('price', 0) > 0:
                new_data = pd.DataFrame([market_info])
                self.data = pd.concat([self.data, new_data])
                # Behalte nur die letzten 24 Stunden
                self.data = self.data.tail(1440)  # 24h * 60min
                logger.info(f"Neue Preisdaten hinzugefügt - Aktueller Preis: {market_info['price']:.2f} USDC")

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Preisdaten: {e}")

    def analyze_trend(self) -> Dict[str, Any]:
        """Analysiert den aktuellen Trend"""
        try:
            if len(self.data) < 2:
                logger.info("Zu wenig Daten für Trendanalyse")
                return {'trend': 'neutral', 'stärke': 0}

            latest_prices = self.data['price'].tail(5)  # 5-Minuten-Trend
            trend = 'aufwärts' if latest_prices.iloc[-1] > latest_prices.iloc[0] else 'abwärts'

            # Berechne die prozentuale Änderung
            strength = abs(latest_prices.iloc[-1] - latest_prices.iloc[0]) / latest_prices.iloc[0] * 100

            logger.info(f"Trendanalyse: {trend}, Stärke: {strength:.2f}%, "
                       f"Von: {latest_prices.iloc[0]:.2f} USDC -> Zu: {latest_prices.iloc[-1]:.2f} USDC")

            return {
                'trend': trend,
                'stärke': strength,
                'letzer_preis': latest_prices.iloc[-1]
            }

        except Exception as e:
            logger.error(f"Fehler bei der Trendanalyse: {e}")
            return {'trend': 'neutral', 'stärke': 0}

    def get_support_resistance(self) -> Dict[str, float]:
        """Berechnet Support und Resistance Levels"""
        try:
            if len(self.data) < 10:
                logger.info("Zu wenig Daten für Support/Resistance Berechnung")
                return {'support': 0, 'resistance': 0}

            prices = self.data['price'].values

            # Berechne Support als 25. Perzentil und Resistance als 75. Perzentil
            support = np.percentile(prices, 25)
            resistance = np.percentile(prices, 75)

            # Prüfe ob die Levels signifikant sind (mindestens 2% Abstand)
            if (resistance - support) / support < 0.02:
                logger.info("Support/Resistance Levels zu eng beieinander")
                return {'support': 0, 'resistance': 0}

            logger.info(f"Support/Resistance berechnet - Support: {support:.2f} USDC, Resistance: {resistance:.2f} USDC")
            return {
                'support': support,
                'resistance': resistance
            }

        except Exception as e:
            logger.error(f"Fehler bei der Support/Resistance Berechnung: {e}")
            return {'support': 0, 'resistance': 0}