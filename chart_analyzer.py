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
            if market_info:
                new_data = pd.DataFrame([market_info])
                self.data = pd.concat([self.data, new_data])

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Preisdaten: {e}")

    def analyze_trend(self) -> Dict[str, Any]:
        """Analysiert den aktuellen Trend"""
        try:
            if len(self.data) < 2:
                return {'trend': 'neutral', 'stärke': 0}

            latest_prices = self.data['price'].tail(10)
            trend = 'aufwärts' if latest_prices.iloc[-1] > latest_prices.iloc[0] else 'abwärts'
            strength = abs(latest_prices.iloc[-1] - latest_prices.iloc[0]) / latest_prices.iloc[0] * 100

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
                return {'support': 0, 'resistance': 0}

            prices = self.data['price'].values
            support = np.percentile(prices, 25)
            resistance = np.percentile(prices, 75)

            return {
                'support': support,
                'resistance': resistance
            }

        except Exception as e:
            logger.error(f"Fehler bei der Support/Resistance Berechnung: {e}")
            return {'support': 0, 'resistance': 0}