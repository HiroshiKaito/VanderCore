import unittest
from datetime import datetime, timedelta
from risk_analyzer import RiskAnalyzer

class TestRiskAnalyzer(unittest.TestCase):
    def setUp(self):
        self.risk_analyzer = RiskAnalyzer()
        # Füge Test-Marktdaten hinzu
        self.test_market_data = {
            'price': 100.0,
            'volume': 1000000.0
        }
        self.risk_analyzer.update_market_data(self.test_market_data)

    def test_position_size_calculation(self):
        """Test der Positionsgrößenberechnung"""
        # Normales Marktvolumen
        account_balance = 1000.0
        current_price = 100.0
        volume_24h = 1000000.0

        position_size, recommendation = self.risk_analyzer.calculate_position_size(
            account_balance, current_price, volume_24h
        )

        # Überprüfe grundlegende Eigenschaften
        self.assertGreater(position_size, 0)
        self.assertLess(position_size, account_balance)
        self.assertIsInstance(recommendation, str)

        # Teste Volumen-Skalierung
        low_volume = 50000.0  # Unter min_volume_requirement
        position_size_low_vol, _ = self.risk_analyzer.calculate_position_size(
            account_balance, current_price, low_volume
        )
        self.assertLess(position_size_low_vol, position_size)

        # Test mit extremem Volumen
        high_volume = 10000000.0
        position_size_high_vol, _ = self.risk_analyzer.calculate_position_size(
            account_balance, current_price, high_volume
        )
        self.assertGreaterEqual(position_size_high_vol, position_size)

    def test_stoploss_calculation(self):
        """Test der Stoploss-Berechnung"""
        entry_price = 100.0

        # Test Long Position
        sl_long, tp_long = self.risk_analyzer.calculate_stoploss(entry_price, 'long')
        self.assertLess(sl_long, entry_price)  # Stoploss unter Eintrittspreis
        self.assertGreater(tp_long, entry_price)  # Takeprofit über Eintrittspreis

        # Test Short Position
        sl_short, tp_short = self.risk_analyzer.calculate_stoploss(entry_price, 'short')
        self.assertGreater(sl_short, entry_price)  # Stoploss über Eintrittspreis
        self.assertLess(tp_short, entry_price)  # Takeprofit unter Eintrittspreis

        # Test mit historischen Daten und hoher Volatilität
        volatile_prices = [
            {'timestamp': datetime.now() - timedelta(hours=i),
             'price': 100.0 * (1 + ((-1)**i * 0.05)),  # ±5% Schwankung
             'volume': 1000000.0}
            for i in range(24)
        ]
        for price_data in volatile_prices:
            self.risk_analyzer.update_market_data(price_data)

        sl_volatile, tp_volatile = self.risk_analyzer.calculate_stoploss(entry_price, 'long')
        self.assertNotEqual(sl_volatile, entry_price * 0.95)  # Sollte nicht der Standard-Wert sein
        self.assertGreater(abs(entry_price - sl_volatile), abs(entry_price - sl_long))  # Weiterer Stoploss bei Volatilität

    def test_risk_analysis(self):
        """Test der Risikoanalyse"""
        # Test mit normaler Transaktion
        amount = 100.0
        wallet_history = [
            {
                'timestamp': datetime.now() - timedelta(hours=1),
                'amount': 50.0,
                'type': 'send'
            }
        ]

        risk_score, recommendations = self.risk_analyzer.analyze_transaction_risk(
            amount, wallet_history
        )

        # Überprüfe Risiko-Score
        self.assertGreaterEqual(risk_score, 0.0)
        self.assertLessEqual(risk_score, 1.0)
        self.assertIsInstance(recommendations, str)

        # Test mit hohem Risiko
        high_risk_history = [
            {'timestamp': datetime.now() - timedelta(minutes=i*5),
             'amount': 50.0,
             'type': 'send'}
            for i in range(12)  # Viele Transaktionen in kurzer Zeit
        ]
        high_risk_score, high_risk_recommendations = self.risk_analyzer.analyze_transaction_risk(
            1000.0,  # Hoher Betrag
            high_risk_history
        )
        self.assertGreater(high_risk_score, risk_score)
        self.assertIn("Hoher Transaktionsbetrag", high_risk_recommendations)

    def test_market_volatility(self):
        """Test der Marktvolatilitätsberechnung"""
        # Test mit stabilen Preisen
        stable_prices = [
            {'timestamp': datetime.now() - timedelta(hours=i),
             'price': 100.0,
             'volume': 1000000.0}
            for i in range(24)
        ]
        for price_data in stable_prices:
            self.risk_analyzer.update_market_data(price_data)

        volatility = self.risk_analyzer._calculate_market_volatility()
        self.assertLess(volatility, 0.5)  # Niedrige Volatilität erwartet

        # Test mit volatilen Preisen
        volatile_prices = [
            {'timestamp': datetime.now() - timedelta(hours=i),
             'price': 100.0 * (1 + ((-1)**i * 0.1)),  # ±10% Schwankung
             'volume': 1000000.0}
            for i in range(24)
        ]
        self.risk_analyzer.historical_data = []  # Reset historical data
        for price_data in volatile_prices:
            self.risk_analyzer.update_market_data(price_data)

        high_volatility = self.risk_analyzer._calculate_market_volatility()
        self.assertGreater(high_volatility, volatility)  # Höhere Volatilität erwartet

if __name__ == '__main__':
    unittest.main()