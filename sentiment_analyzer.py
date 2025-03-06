import logging
from textblob import TextBlob
import requests
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        """Initialisiert den Sentiment Analyzer"""
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.dex_screener_api = "https://api.dexscreener.com/latest"
        self.nitter_api = "https://nitter.cz/search"

    async def analyze_market_sentiment(self) -> dict:
        """Analysiert die Marktstimmung aus verschiedenen Quellen"""
        try:
            sentiment_data = {
                'overall_score': 0,
                'sources': {},
                'timestamp': datetime.now().isoformat()
            }

            # CoinGecko Sentiment
            coingecko_data = await self._fetch_coingecko_data()
            if coingecko_data:
                sentiment_data['sources']['coingecko'] = self._analyze_coingecko_sentiment(coingecko_data)

            # Social Media Sentiment (Nitter/Twitter)
            social_data = await self._fetch_social_data()
            if social_data:
                sentiment_data['sources']['social'] = self._analyze_social_sentiment(social_data)

            # DEX Screener Marktdaten
            dex_data = await self._fetch_dex_data()
            if dex_data:
                sentiment_data['sources']['dex'] = self._analyze_dex_sentiment(dex_data)

            # Berechne Gesamtscore
            scores = [source['score'] for source in sentiment_data['sources'].values()]
            if scores:
                sentiment_data['overall_score'] = sum(scores) / len(scores)

            logger.info(f"Sentiment Analyse abgeschlossen - Score: {sentiment_data['overall_score']:.2f}")
            return sentiment_data

        except Exception as e:
            logger.error(f"Fehler bei der Sentiment-Analyse: {e}")
            return {'overall_score': 0, 'sources': {}, 'error': str(e)}

    async def _fetch_coingecko_data(self) -> dict:
        """Holt Solana-Daten von CoinGecko"""
        try:
            response = requests.get(
                f"{self.coingecko_api}/simple/price",
                params={
                    'ids': 'solana',
                    'vs_currencies': 'usd',
                    'include_24hr_vol': True,
                    'include_24hr_change': True,
                    'include_last_updated_at': True
                },
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"CoinGecko API Fehler: {response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der CoinGecko-Daten: {e}")
            return {}

    async def _fetch_social_data(self) -> list:
        """Holt Social Media Daten über Nitter"""
        try:
            params = {
                'f': 'tweets',
                'q': 'solana language:de OR language:en',
                'since': '24h'
            }
            response = requests.get(self.nitter_api, params=params, timeout=15)
            if response.status_code == 200:
                return response.text
            logger.warning(f"Nitter API Fehler: {response.status_code}")
            return []
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Social Media Daten: {e}")
            return []

    async def _fetch_dex_data(self) -> dict:
        """Holt DEX-Daten für Solana"""
        try:
            response = requests.get(
                f"{self.dex_screener_api}/pairs/solana",
                timeout=15
            )
            if response.status_code == 200:
                return response.json()
            logger.warning(f"DEX Screener API Fehler: {response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Fehler beim Abrufen der DEX-Daten: {e}")
            return {}

    def _analyze_coingecko_sentiment(self, data: dict) -> dict:
        """Analysiert CoinGecko Daten für Sentiment"""
        try:
            if 'solana' not in data:
                return {'score': 0, 'confidence': 0}

            sol_data = data['solana']
            price_change = sol_data.get('usd_24h_change', 0)
            volume = sol_data.get('usd_24h_vol', 0)

            # Sentiment Score basierend auf Preis und Volumen
            price_sentiment = 0.5 + (price_change / 20)  # Normalisiert auf -0.5 bis 1.5
            volume_factor = min(volume / 1000000000, 1)  # Normalisiert auf 0-1

            score = (price_sentiment * 0.7 + volume_factor * 0.3)
            score = max(0, min(1, score))  # Begrenzt auf 0-1

            return {
                'score': score,
                'confidence': 0.8,
                'metrics': {
                    'price_change': price_change,
                    'volume': volume
                }
            }

        except Exception as e:
            logger.error(f"Fehler bei der CoinGecko Sentiment-Analyse: {e}")
            return {'score': 0, 'confidence': 0}

    def _analyze_social_sentiment(self, text_data: str) -> dict:
        """Analysiert Social Media Text mit TextBlob"""
        try:
            blob = TextBlob(text_data)
            sentiment_scores = []

            for sentence in blob.sentences:
                sentiment_scores.append(sentence.sentiment.polarity)

            if not sentiment_scores:
                return {'score': 0.5, 'confidence': 0}

            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            normalized_score = (avg_sentiment + 1) / 2  # Konvertiert von [-1,1] zu [0,1]

            return {
                'score': normalized_score,
                'confidence': min(len(sentiment_scores) / 10, 1),  # Konfidenz basierend auf Datenmenge
                'metrics': {
                    'sample_size': len(sentiment_scores),
                    'raw_sentiment': avg_sentiment
                }
            }

        except Exception as e:
            logger.error(f"Fehler bei der Social Media Sentiment-Analyse: {e}")
            return {'score': 0.5, 'confidence': 0}

    def _analyze_dex_sentiment(self, data: dict) -> dict:
        """Analysiert DEX-Daten für Sentiment"""
        try:
            if 'pairs' not in data:
                return {'score': 0.5, 'confidence': 0}

            sol_pairs = [
                pair for pair in data['pairs']
                if pair.get('baseToken', {}).get('symbol', '').upper() == 'SOL'
            ]

            if not sol_pairs:
                return {'score': 0.5, 'confidence': 0}

            # Analysiere Handelsaktivität
            total_volume = sum(float(pair.get('volume', {}).get('h24', 0)) for pair in sol_pairs)
            price_changes = [
                float(pair.get('priceChange', {}).get('h24', 0))
                for pair in sol_pairs
            ]

            avg_price_change = sum(price_changes) / len(price_changes) if price_changes else 0
            volume_score = min(total_volume / 100000000, 1)  # Normalisiert auf 0-1
            price_score = 0.5 + (avg_price_change / 20)  # Normalisiert auf 0-1

            score = (volume_score * 0.4 + price_score * 0.6)
            score = max(0, min(1, score))

            return {
                'score': score,
                'confidence': 0.7,
                'metrics': {
                    'total_volume': total_volume,
                    'avg_price_change': avg_price_change,
                    'pair_count': len(sol_pairs)
                }
            }

        except Exception as e:
            logger.error(f"Fehler bei der DEX Sentiment-Analyse: {e}")
            return {'score': 0.5, 'confidence': 0}
