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
        account_balance = 1000.0
        current_price = 100.0
        volume_24h = 1000000.0

        position_size, recommendation = self.risk_analyzer.calculate_position_size(
            account_balance, current_price, volume_24h
        )

        self.assertGreater(position_size, 0)
        self.assertLess(position_size, account_balance)
        self.assertIsInstance(recommendation, str)

    def test_stoploss_calculation(self):
        entry_price = 100.0

        # Test Long Position
        sl_long, tp_long = self.risk_analyzer.calculate_stoploss(entry_price, 'long')
        self.assertLess(sl_long, entry_price)
        self.assertGreater(tp_long, entry_price)

        # Test Short Position
        sl_short, tp_short = self.risk_analyzer.calculate_stoploss(entry_price, 'short')
        self.assertGreater(sl_short, entry_price)
        self.assertLess(tp_short, entry_price)

    def test_risk_analysis(self):
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

        self.assertGreaterEqual(risk_score, 0.0)
        self.assertLessEqual(risk_score, 1.0)
        self.assertIsInstance(recommendations, str)

if __name__ == '__main__':
    unittest.main()