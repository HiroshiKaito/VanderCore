import unittest
from datetime import datetime
import asyncio
from sentiment_analyzer import SentimentAnalyzer
import nltk

class TestSentimentAnalyzer(unittest.TestCase):
    def setUp(self):
        """Test Setup mit NLTK Download"""
        try:
            nltk.data.find('sentiment/vader_lexicon.zip')
        except LookupError:
            nltk.download('vader_lexicon')
        self.analyzer = SentimentAnalyzer()

    def test_text_sentiment(self):
        """Test der kombinierten Textanalyse"""
        # Test mit positivem Text
        positive_text = "Solana is performing exceptionally well. Great progress and innovation."
        positive_result = self.analyzer._analyze_text_sentiment(positive_text)

        self.assertIsInstance(positive_result, dict)
        self.assertIn('score', positive_result)
        self.assertIn('confidence', positive_result)
        self.assertTrue(positive_result['score'] > 0.5)

        # Test mit negativem Text
        negative_text = "Solana network is having issues. Poor performance today."
        negative_result = self.analyzer._analyze_text_sentiment(negative_text)

        self.assertTrue(negative_result['score'] < 0.5)

    def test_combined_sentiment(self):
        """Test der kombinierten Sentiment-Analyse"""
        async def run_test():
            result = await self.analyzer.analyze_market_sentiment()

            self.assertIsInstance(result, dict)
            self.assertIn('overall_score', result)
            self.assertIn('sources', result)
            self.assertTrue(0 <= result['overall_score'] <= 1)

            # Prüfe Quellen
            sources = result['sources']
            self.assertIsInstance(sources, dict)
            for source in ['coingecko', 'social', 'dex']:
                if source in sources:
                    self.assertIn('score', sources[source])
                    self.assertIn('confidence', sources[source])

        asyncio.run(run_test())

    def test_empty_data_handling(self):
        """Test der Fehlerbehandlung bei leeren Daten"""
        # Test mit leerem Text
        empty_result = self.analyzer._analyze_text_sentiment("")
        self.assertEqual(empty_result['score'], 0.5)
        self.assertGreaterEqual(empty_result['confidence'], 0)

    def test_error_handling(self):
        """Test der Fehlerbehandlung"""
        # Test mit None
        none_result = self.analyzer._analyze_text_sentiment(None)
        self.assertEqual(none_result['score'], 0.5)
        self.assertEqual(none_result['confidence'], 0)

        # Test mit invaliden Daten
        invalid_result = self.analyzer._analyze_text_sentiment(123)
        self.assertEqual(invalid_result['score'], 0.5)
        self.assertEqual(invalid_result['confidence'], 0)

    def test_dex_data_fetching(self):
        """Test der DEX Daten Abrufung"""
        async def run_test():
            # Test mit leeren Daten
            empty_result = await self.analyzer._fetch_dex_data()
            self.assertIn('pairs', empty_result)
            self.assertIsInstance(empty_result['pairs'], list)

            # Test der Sentiment-Analyse mit DEX-Daten
            test_data = {
                'pairs': [{
                    'baseToken': {'symbol': 'SOL'},
                    'quoteToken': {'symbol': 'USDC'},
                    'priceUsd': '100.0',
                    'volume': {'h24': '1000000'},
                    'priceChange': {'h24': '2.5'}
                }]
            }

            sentiment = self.analyzer._analyze_dex_sentiment(test_data)
            self.assertIsInstance(sentiment, dict)
            self.assertIn('score', sentiment)
            self.assertIn('confidence', sentiment)
            self.assertGreaterEqual(sentiment['score'], 0)
            self.assertLessEqual(sentiment['score'], 1)

        asyncio.run(run_test())

    def test_api_error_handling(self):
        """Test der API Fehlerbehandlung"""
        async def run_test():
            # Test mit ungültiger API URL
            self.analyzer.dex_screener_api = "https://invalid-url"
            result = await self.analyzer._fetch_dex_data()
            self.assertIn('pairs', result)
            self.assertEqual(len(result['pairs']), 0)

            # Test mit Timeout
            self.analyzer.timeout = 0.001
            result = await self.analyzer._fetch_dex_data()
            self.assertIn('pairs', result)
            self.assertEqual(len(result['pairs']), 0)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()