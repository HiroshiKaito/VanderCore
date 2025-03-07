import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from automated_signal_generator import AutomatedSignalGenerator
from dex_connector import DexConnector
from signal_processor import SignalProcessor
from unittest.mock import MagicMock, patch

class TestAutomatedSignalGenerator(unittest.TestCase):
    def setUp(self):
        """Test Setup mit Mock-Objekten"""
        self.dex_connector = MagicMock(spec=DexConnector)
        self.signal_processor = MagicMock(spec=SignalProcessor)
        self.bot = MagicMock()
        self.bot.active_users = [12345]  # Test User ID
        
        self.generator = AutomatedSignalGenerator(
            self.dex_connector,
            self.signal_processor,
            self.bot
        )

        # Mock Marktdaten
        self.market_data = {
            'price': 100.0,
            'volume': 1000000.0,
            'timestamp': datetime.now()
        }
        self.dex_connector.get_market_info.return_value = self.market_data

    def test_signal_generation(self):
        """Test der Signal-Generierung"""
        # Erstelle Test-Marktdaten mit aufsteigendem Trend
        dates = pd.date_range(start='2025-01-01', end='2025-01-02', freq='5min')
        test_data = pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(len(dates))],
            'high': [100 + i * 0.15 for i in range(len(dates))],
            'low': [100 + i * 0.05 for i in range(len(dates))],
            'close': [100 + i * 0.1 for i in range(len(dates))],
            'volume': [1000000 + i * 1000 for i in range(len(dates))],
            'timestamp': dates
        })

        # Update Chart Data
        self.generator.chart_analyzer.data = test_data

        # Generiere Signal
        self.generator.generate_signals()

        # Überprüfe ob Signal-Processor aufgerufen wurde
        self.assertTrue(self.signal_processor.process_signal.called)
        
        # Hole die Argumente des letzten Aufrufs
        signal_args = self.signal_processor.process_signal.call_args[0][0]
        
        # Überprüfe Signal-Eigenschaften
        self.assertIn('direction', signal_args)
        self.assertIn('entry', signal_args)
        self.assertIn('stop_loss', signal_args)
        self.assertIn('take_profit', signal_args)
        self.assertIn('signal_quality', signal_args)

    def test_quality_calculation(self):
        """Test der Signal-Qualitätsberechnung"""
        trend_analysis = {
            'trend': 'aufwärts',
            'stärke': 0.8,
            'metriken': {
                'momentum': 0.5,
                'volatilität': 0.2,
                'volumen_trend': 0.3
            }
        }
        
        quality = self.generator._calculate_signal_quality(
            trend_analysis=trend_analysis,
            strength=0.8,
            expected_profit=2.0
        )
        
        # Überprüfe Qualitätsscore
        self.assertGreaterEqual(quality, 0)
        self.assertLessEqual(quality, 10)
        self.assertIsInstance(quality, float)

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
        test_signal = {
            'pair': 'SOL/USD',
            'direction': 'long',
            'entry': 100.0,
            'stop_loss': 98.0,
            'take_profit': 105.0,
            'expected_profit': 5.0,
            'signal_quality': 8.5,
            'trend_strength': 0.8
        }
        
        # Mock für bot.updater.bot.send_photo
        with patch.object(self.bot.updater.bot, 'send_photo') as mock_send_photo:
            self.generator._notify_users_about_signal(test_signal)
            
            # Überprüfe ob Benachrichtigung gesendet wurde
            self.assertTrue(mock_send_photo.called)
            
            # Überprüfe Benachrichtigungsdetails
            call_args = mock_send_photo.call_args
            self.assertIn('chat_id', call_args[1])
            self.assertIn('caption', call_args[1])
            self.assertIn('reply_markup', call_args[1])

    def tearDown(self):
        """Cleanup nach Tests"""
        self.generator.stop()

if __name__ == '__main__':
    unittest.main()
