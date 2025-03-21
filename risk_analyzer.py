import logging
from typing import Dict, Any, List, Tuple
import numpy as np
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class RiskAnalyzer:
    def __init__(self):
        self.risk_scores: Dict[str, float] = {}
        self.historical_data: List[Dict[str, Any]] = []
        self.volatility_threshold = 0.1  # 10% Schwankung als Basis
        self.max_position_size = 0.1  # Maximal 10% des Portfolios pro Trade
        self.min_volume_requirement = 100000  # Mindestvolumen in USDC

    def calculate_position_size(self, account_balance: float, 
                              current_price: float, 
                              volume_24h: float) -> Tuple[float, str]:
        """Berechnet die optimale Positionsgröße basierend auf Volumen und Risiko"""
        try:
            # Volumen-basierte Skalierung
            volume_scale = min(volume_24h / self.min_volume_requirement, 1.0)

            # Maximale Position basierend auf Account-Balance
            max_position = account_balance * self.max_position_size

            # Skaliere Position basierend auf Volumen
            suggested_position = max_position * volume_scale

            # Berechne Anzahl der Token
            token_amount = suggested_position / current_price

            recommendation = (
                f"💡 Empfohlene Position: {suggested_position:.2f} USDC\n"
                f"🔢 Token-Menge: {token_amount:.4f} SOL\n"
                f"📊 Volumen-Faktor: {volume_scale:.2%}"
            )

            return suggested_position, recommendation

        except Exception as e:
            logger.error(f"Fehler bei der Positionsgrößenberechnung: {e}")
            return 0.0, "Fehler bei der Berechnung"

    def calculate_stoploss(self, entry_price: float, direction: str = 'long') -> Tuple[float, float]:
        """Berechnet Stoploss basierend auf Volatilität und Marktbedingungen"""
        try:
            if not self.historical_data:
                return entry_price * 0.95, entry_price * 1.05  # Standard 5% SL/TP

            # Berechne Volatilität
            prices = [data['price'] for data in self.historical_data[-24:]]  # 24h Daten
            volatility = np.std(prices) / np.mean(prices)

            # Dynamische Stoploss-Berechnung
            if direction == 'long':
                stoploss = entry_price * (1 - max(volatility * 2, 0.02))  # Mindestens 2%
                takeprofit = entry_price * (1 + max(volatility * 3, 0.03))  # Mindestens 3%
            else:  # Short
                stoploss = entry_price * (1 + max(volatility * 2, 0.02))
                takeprofit = entry_price * (1 - max(volatility * 3, 0.03))

            return stoploss, takeprofit

        except Exception as e:
            logger.error(f"Fehler bei der Stoploss-Berechnung: {e}")
            return entry_price * 0.95, entry_price * 1.05

    def analyze_transaction_risk(self, amount: float, wallet_history: List[Dict[str, Any]]) -> Tuple[float, str]:
        """Analysiert das Risiko einer Transaktion basierend auf verschiedenen Faktoren"""
        try:
            # Grundlegende Risikofaktoren
            risk_factors = {
                'amount_risk': self._calculate_amount_risk(amount),
                'time_risk': self._calculate_time_risk(),
                'history_risk': self._analyze_wallet_history(wallet_history),
                'market_volatility': self._calculate_market_volatility()
            }

            # Gewichtete Risikoberechnung
            total_risk = sum(risk_factors.values()) / len(risk_factors)
            risk_level = self._determine_risk_level(total_risk)

            recommendations = self._generate_recommendations(risk_factors)

            return total_risk, recommendations

        except Exception as e:
            logger.error(f"Fehler bei der Risikoanalyse: {e}")
            return 1.0, "Fehler bei der Risikoberechnung"

    def _calculate_amount_risk(self, amount: float) -> float:
        """Berechnet das Risiko basierend auf der Transaktionshöhe"""
        try:
            # Beispiel: Höhere Beträge = höheres Risiko
            base_risk = min(amount / 10.0, 1.0)  # Normalisiert auf 0-1
            return base_risk
        except Exception as e:
            logger.error(f"Fehler bei der Betragsrisikoberechnung: {e}")
            return 0.5

    def _calculate_time_risk(self) -> float:
        """Berechnet das Risiko basierend auf der Tageszeit"""
        try:
            current_hour = datetime.now().hour
            # Höheres Risiko während typischer Schlafenszeiten
            if 1 <= current_hour <= 5:
                return 0.8
            # Moderates Risiko während der Haupthandelszeiten
            elif 9 <= current_hour <= 17:
                return 0.3
            return 0.5
        except Exception as e:
            logger.error(f"Fehler bei der Zeitrisikoberechnung: {e}")
            return 0.5

    def _analyze_wallet_history(self, wallet_history: List[Dict[str, Any]]) -> float:
        """Analysiert das Wallet-Verhalten für Risikoeinschätzung"""
        try:
            if not wallet_history:
                return 0.5

            # Analyse der letzten Transaktionen
            recent_transactions = len([tx for tx in wallet_history 
                                    if datetime.now() - tx['timestamp'] < timedelta(days=1)])

            # Hohes Risiko bei vielen schnellen Transaktionen
            if recent_transactions > 10:
                return 0.8
            elif recent_transactions > 5:
                return 0.5
            return 0.3

        except Exception as e:
            logger.error(f"Fehler bei der Wallet-Historienanalyse: {e}")
            return 0.5

    def _calculate_market_volatility(self) -> float:
        """Berechnet das Marktvolatilitätsrisiko"""
        try:
            if not self.historical_data:
                return 0.5

            prices = [data['price'] for data in self.historical_data[-24:]]  # Letzte 24 Datenpunkte
            if len(prices) < 2:
                return 0.5

            volatility = np.std(prices) / np.mean(prices)
            return min(volatility / self.volatility_threshold, 1.0)

        except Exception as e:
            logger.error(f"Fehler bei der Volatilitätsberechnung: {e}")
            return 0.5

    def _determine_risk_level(self, risk_score: float) -> str:
        """Bestimmt das Risikolevel basierend auf dem Score"""
        if risk_score < 0.3:
            return "NIEDRIG"
        elif risk_score < 0.6:
            return "MITTEL"
        else:
            return "HOCH"

    def _generate_recommendations(self, risk_factors: Dict[str, float]) -> str:
        """Generiert Handlungsempfehlungen basierend auf den Risikofaktoren"""
        recommendations = []

        if risk_factors['amount_risk'] > 0.7:
            recommendations.append("⚠️ Hoher Transaktionsbetrag - Erwägen Sie die Aufteilung in kleinere Beträge")

        if risk_factors['time_risk'] > 0.7:
            recommendations.append("⏰ Ungünstiger Zeitpunkt - Erhöhtes Risiko außerhalb der Haupthandelszeiten")

        if risk_factors['history_risk'] > 0.7:
            recommendations.append("📊 Ungewöhnliche Aktivität - Überprüfen Sie Ihre letzten Transaktionen")

        if risk_factors['market_volatility'] > 0.7:
            recommendations.append("📈 Hohe Marktvolatilität - Vorsicht bei großen Transaktionen")

        if not recommendations:
            recommendations.append("✅ Keine besonderen Risikohinweise")

        return "\n".join(recommendations)

    def update_market_data(self, price_data: Dict[str, Any]):
        """Aktualisiert die Marktdaten für Volatilitätsberechnungen"""
        try:
            self.historical_data.append({
                'timestamp': datetime.now(),
                'price': float(price_data['price']),
                'volume': float(price_data.get('volume', 0))
            })

            # Behalte nur die letzten 24 Stunden
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.historical_data = [data for data in self.historical_data 
                                  if data['timestamp'] > cutoff_time]

        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Marktdaten: {e}")