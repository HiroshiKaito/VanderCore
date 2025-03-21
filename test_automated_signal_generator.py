import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from automated_signal_generator import AutomatedSignalGenerator
from dex_connector import DexConnector
from signal_processor import SignalProcessor
from unittest.mock import MagicMock, patch, PropertyMock
from chart_analyzer import ChartAnalyzer

class TestAutomatedSignalGenerator(unittest.TestCase):
    def setUp(self):
        """Test Setup mit Mock-Objekten"""
        self.dex_connector = MagicMock(spec=DexConnector)
        self.signal_processor = MagicMock(spec=SignalProcessor)
        self.bot = MagicMock()
        self.bot.active_users = [12345]  # Test User ID

        # Mock Chart Analyzer
        self.chart_analyzer = MagicMock(spec=ChartAnalyzer)

        self.generator = AutomatedSignalGenerator(
            self.dex_connector,
            self.signal_processor,
            self.bot
        )
        self.generator.chart_analyzer = self.chart_analyzer

        # Mock Marktdaten
        self.market_data = {
            'price': 100.0,
            'volume': 1000000.0,
            'timestamp': datetime.now()
        }
        self.dex_connector.get_market_info.return_value = self.market_data

    def test_signal_filtering(self):
        """Test der Signal-Filterung"""
        # Test mit schwachem Signal
        weak_trend = {
            'trend': 'aufwärts',
            'stärke': 0.01,  # Sehr schwacher Trend
            'metriken': {
                'momentum': 0.1,
                'volatilität': 0.1,
                'volumen_trend': 0.1
            }
        }

        # Mock der Zeitstempel-Generierung
        with patch('time.time', return_value=1741471528.241259):
            signal = self.generator._create_signal_from_analysis(
                current_price=100.0,
                trend_analysis=weak_trend,
                support_resistance={'support': 98.0, 'resistance': 102.0}
            )

            # Schwaches Signal sollte gefiltert werden
            self.assertIsNone(signal)

            # Test mit starkem Signal
            strong_trend = {
                'trend': 'aufwärts',
                'stärke': 0.8,
                'metriken': {
                    'momentum': 0.7,
                    'volatilität': 0.2,
                    'volumen_trend': 0.5
                }
            }

            signal = self.generator._create_signal_from_analysis(
                current_price=100.0,
                trend_analysis=strong_trend,
                support_resistance={'support': 98.0, 'resistance': 102.0}
            )

            # Starkes Signal sollte akzeptiert werden
            self.assertIsNotNone(signal)
            self.assertIn('signal_quality', signal)
            self.assertGreater(signal['signal_quality'], 5)

    def test_notification_system(self):
        """Test des Benachrichtigungssystems"""
        # Mock die Chart-Erstellung
        self.chart_analyzer.create_prediction_chart.return_value = b"mock_chart_data"

        # Mock für bot.updater.bot.send_photo
        mock_bot = MagicMock()
        mock_bot.send_photo = MagicMock()

        self.bot.updater = MagicMock()
        self.bot.updater.bot = mock_bot

        # Test Signal mit allen erforderlichen Feldern
        test_signal = {
            'pair': 'SOL/USD',
            'direction': 'long',
            'entry': 100.0,
            'stop_loss': 98.0,
            'take_profit': 105.0,
            'expected_profit': 5.0,
            'signal_quality': 8.5,
            'trend_strength': 0.8,
            'timestamp': datetime.now().timestamp()
        }

        # Mock die Wallet-Manager-Methode
        self.bot.wallet_manager = MagicMock()
        self.bot.wallet_manager.get_balance.return_value = 10.0

        self.generator._notify_users_about_signal(test_signal)

        # Überprüfe ob Benachrichtigung gesendet wurde
        self.assertTrue(mock_bot.send_photo.called)

        # Überprüfe Benachrichtigungsdetails
        call_args = mock_bot.send_photo.call_args
        self.assertIn('chat_id', call_args[1])
        self.assertIn('caption', call_args[1])
        self.assertIn('reply_markup', call_args[1])

    def tearDown(self):
        """Cleanup nach Tests"""
        self.generator.stop()

if __name__ == '__main__':
    unittest.main()