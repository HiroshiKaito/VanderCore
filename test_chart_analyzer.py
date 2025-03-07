import unittest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from chart_analyzer import ChartAnalyzer

class TestChartAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = ChartAnalyzer()
        # Erstelle Test-Daten
        dates = pd.date_range(start='2025-01-01', end='2025-01-02', freq='1min')
        self.test_data = pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(len(dates))],
            'high': [100 + i * 0.15 for i in range(len(dates))],
            'low': [100 + i * 0.05 for i in range(len(dates))],
            'close': [100 + i * 0.1 for i in range(len(dates))],
            'volume': [1000000 + i * 1000 for i in range(len(dates))],
            'timestamp': dates
        })
        self.analyzer.data = self.test_data

    def test_trend_analysis(self):
        """Test der Trendanalyse"""
        result = self.analyzer.analyze_trend()
        
        self.assertIn('trend', result)
        self.assertIn('stärke', result)
        self.assertIn('metriken', result)
        
        # Überprüfe Trend-Richtung
        self.assertEqual(result['trend'], 'aufwärts')  # Sollte aufwärts sein wegen steigender Preise
        self.assertGreater(result['stärke'], 0)  # Sollte positive Stärke haben
        
        # Überprüfe Metriken
        metrics = result['metriken']
        self.assertGreater(metrics['preis_änderung'], 0)
        self.assertGreater(metrics['volumen_trend'], 0)

    def test_support_resistance(self):
        """Test der Support/Resistance Berechnung"""
        result = self.analyzer.get_support_resistance()
        
        self.assertIn('support', result)
        self.assertIn('resistance', result)
        
        # Überprüfe Verhältnis
        self.assertLess(result['support'], result['resistance'])
        
        # Überprüfe ob Levels im Preisbereich liegen
        min_price = self.test_data['low'].min()
        max_price = self.test_data['high'].max()
        self.assertGreaterEqual(result['support'], min_price * 0.95)
        self.assertLessEqual(result['resistance'], max_price * 1.05)

    def test_prediction_chart(self):
        """Test der Chart-Erstellung"""
        entry_price = 100.0
        target_price = 105.0
        stop_loss = 98.0
        
        chart_data = self.analyzer.create_prediction_chart(
            entry_price=entry_price,
            target_price=target_price,
            stop_loss=stop_loss
        )
        
        # Überprüfe ob Chart erstellt wurde
        self.assertIsNotNone(chart_data)
        self.assertIsInstance(chart_data, bytes)
        self.assertGreater(len(chart_data), 0)

    def test_empty_data_handling(self):
        """Test des Verhaltens bei leeren Daten"""
        empty_analyzer = ChartAnalyzer()
        
        # Teste Trendanalyse
        trend_result = empty_analyzer.analyze_trend()
        self.assertEqual(trend_result['trend'], 'neutral')
        self.assertEqual(trend_result['stärke'], 0)
        
        # Teste Support/Resistance
        sr_result = empty_analyzer.get_support_resistance()
        self.assertEqual(sr_result['support'], 0)
        self.assertEqual(sr_result['resistance'], 0)
        
        # Teste Chart-Erstellung
        chart_result = empty_analyzer.create_prediction_chart(100, 105, 95)
        self.assertIsNone(chart_result)

if __name__ == '__main__':
    unittest.main()
