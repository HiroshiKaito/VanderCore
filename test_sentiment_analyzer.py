import unittest
from datetime import datetime, timedelta
import asyncio
from sentiment_analyzer import SentimentAnalyzer

class TestSentimentAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = SentimentAnalyzer()

    def test_coingecko_sentiment(self):
        # Test-Daten
        test_data = {
            'solana': {
                'usd_24h_change': 5.0,  # 5% Steigerung
                'usd_24h_vol': 500000000  # 500M Volumen
            }
        }
        
        result = self.analyzer._analyze_coingecko_sentiment(test_data)
        
        self.assertIsInstance(result, dict)
        self.assertIn('score', result)
        self.assertIn('confidence', result)
        self.assertTrue(0 <= result['score'] <= 1)
        self.assertTrue(0 <= result['confidence'] <= 1)

    def test_social_sentiment(self):
        # Test mit positivem Text
        positive_text = "Solana is performing exceptionally well. Great progress and innovation."
        positive_result = self.analyzer._analyze_social_sentiment(positive_text)
        
        self.assertIsInstance(positive_result, dict)
        self.assertIn('score', positive_result)
        self.assertTrue(positive_result['score'] > 0.5)  # Sollte positiv sein

        # Test mit negativem Text
        negative_text = "Solana network is having issues. Poor performance today."
        negative_result = self.analyzer._analyze_social_sentiment(negative_text)
        
        self.assertTrue(negative_result['score'] < 0.5)  # Sollte negativ sein

    def test_dex_sentiment(self):
        # Test-Daten
        test_data = {
            'pairs': [
                {
                    'baseToken': {'symbol': 'SOL'},
                    'volume': {'h24': '1000000'},
                    'priceChange': {'h24': '2.5'}
                }
            ]
        }
        
        result = self.analyzer._analyze_dex_sentiment(test_data)
        
        self.assertIsInstance(result, dict)
        self.assertIn('score', result)
        self.assertIn('confidence', result)
        self.assertTrue(0 <= result['score'] <= 1)

    def test_empty_data_handling(self):
        # Test mit leeren Daten
        empty_coingecko = self.analyzer._analyze_coingecko_sentiment({})
        empty_social = self.analyzer._analyze_social_sentiment("")
        empty_dex = self.analyzer._analyze_dex_sentiment({})
        
        # Alle sollten neutrale Scores zurückgeben
        self.assertEqual(empty_coingecko['score'], 0.5)
        self.assertEqual(empty_social['score'], 0.5)
        self.assertEqual(empty_dex['score'], 0.5)

    def test_full_sentiment_analysis(self):
        async def run_test():
            result = await self.analyzer.analyze_market_sentiment()
            
            self.assertIsInstance(result, dict)
            self.assertIn('overall_score', result)
            self.assertIn('sources', result)
            self.assertTrue(0 <= result['overall_score'] <= 1)

        # Führe den async Test aus
        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
