import logging
from textblob import TextBlob
import requests
from datetime import datetime, timedelta
import json
from typing import Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        """Initialisiert den Sentiment Analyzer"""
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.dex_screener_api = "https://api.dexscreener.com/latest"
        self.nitter_api = "https://nitter.cz/search"

        # API Konfiguration
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; SolanaBot/1.0)',
            'Accept': 'application/json'
        }

        # Retry Konfiguration
        self.max_retries = 3
        self.retry_delay = 2  # Sekunden
        self.timeout = 15  # Sekunden

    async def analyze_market_sentiment(self) -> dict:
        """Analysiert die Marktstimmung aus verschiedenen Quellen"""
        try:
            sentiment_data = {
                'overall_score': 0,
                'sources': {},
                'timestamp': datetime.now().isoformat()
            }

            # Parallele API-Aufrufe
            tasks = [
                self._fetch_coingecko_data(),
                self._fetch_social_data(),
                self._fetch_dex_data()
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Verarbeite die Ergebnisse
            if isinstance(results[0], dict):
                sentiment_data['sources']['coingecko'] = self._analyze_coingecko_sentiment(results[0])

            if isinstance(results[1], str):
                sentiment_data['sources']['social'] = self._analyze_social_sentiment(results[1])

            if isinstance(results[2], dict):
                sentiment_data['sources']['dex'] = self._analyze_dex_sentiment(results[2])

            # Berechne Gesamtscore mit Gewichtung
            scores = []
            weights = {'coingecko': 0.4, 'social': 0.3, 'dex': 0.3}

            for source, data in sentiment_data['sources'].items():
                if isinstance(data, dict) and data.get('confidence', 0) > 0:
                    scores.append(data['score'] * weights.get(source, 0.3))

            if scores:
                sentiment_data['overall_score'] = sum(scores) / sum(weights.values())
                logger.info(f"Sentiment Analyse abgeschlossen - Score: {sentiment_data['overall_score']:.2f}")
            else:
                sentiment_data['overall_score'] = 0.5
                logger.warning("Keine validen Sentiment-Daten gefunden, verwende neutralen Score")

            return sentiment_data

        except Exception as e:
            logger.error(f"Fehler bei der Sentiment-Analyse: {e}")
            return {'overall_score': 0.5, 'sources': {}, 'error': str(e)}

    async def _fetch_with_retry(self, url: str, params: Dict = None) -> Optional[requests.Response]:
        """Generische Fetch-Funktion mit Retry-Mechanismus"""
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    return response

                if response.status_code == 429:  # Rate Limit
                    wait_time = self.retry_delay * (2 ** attempt)
                    logger.warning(f"Rate Limit erreicht - Warte {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue

                logger.warning(f"API Fehler: {response.status_code} für URL: {url}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue

                return None

            except requests.exceptions.RequestException as e:
                logger.error(f"Request Fehler für {url}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(self.retry_delay)
                    continue
                return None

        return None

    async def _fetch_coingecko_data(self) -> Dict[str, Any]:
        """Holt Solana-Daten von CoinGecko mit Retry-Mechanismus"""
        try:
            response = await self._fetch_with_retry(
                f"{self.coingecko_api}/simple/price",
                params={
                    'ids': 'solana',
                    'vs_currencies': 'usd',
                    'include_24hr_vol': True,
                    'include_24hr_change': True,
                    'include_last_updated_at': True
                }
            )

            if response:
                data = response.json()
                if 'solana' in data:
                    logger.info("CoinGecko Daten erfolgreich abgerufen")
                    return data
                logger.warning("Unerwartetes CoinGecko Datenformat")

            return {}

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der CoinGecko-Daten: {e}")
            return {}

    async def _fetch_social_data(self) -> str:
        """Holt Social Media Daten über Nitter"""
        try:
            response = await self._fetch_with_retry(
                self.nitter_api,
                params={
                    'f': 'tweets',
                    'q': 'solana language:de OR language:en',
                    'since': '24h'
                }
            )

            if response:
                logger.info("Social Media Daten erfolgreich abgerufen")
                return response.text

            return ""

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Social Media Daten: {e}")
            return ""

    async def _fetch_dex_data(self) -> Dict[str, Any]:
        """Holt DEX-Daten für Solana mit Retry-Mechanismus"""
        try:
            # Versuche zuerst die Token-spezifische API
            response = await self._fetch_with_retry(
                f"{self.dex_screener_api}/pairs/solana/So11111111111111111111111111111111111111112"
            )

            if response:
                data = response.json()
                if 'pairs' in data:
                    logger.info("DEX Daten erfolgreich abgerufen")
                    return data

            # Fallback auf die allgemeine Pairs API
            response = await self._fetch_with_retry(
                f"{self.dex_screener_api}/pairs/solana"
            )

            if response:
                data = response.json()
                if 'pairs' in data:
                    logger.info("DEX Daten (Fallback) erfolgreich abgerufen")
                    return data
                logger.warning("Unerwartetes DEX Screener Datenformat")

            return {}

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der DEX-Daten: {e}")
            return {}

    def _analyze_coingecko_sentiment(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analysiert CoinGecko Daten für Sentiment"""
        try:
            if 'solana' not in data:
                return {'score': 0.5, 'confidence': 0}

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
            return {'score': 0.5, 'confidence': 0}

    def _analyze_social_sentiment(self, text_data: str) -> Dict[str, Any]:
        """Analysiert Social Media Text mit TextBlob"""
        try:
            if not text_data:
                return {'score': 0.5, 'confidence': 0}

            # Bereinige Text und bereite ihn für die Analyse vor
            text_data = ' '.join(text_data.split())  # Normalisiere Whitespace
            text_data = text_data.replace('\n', ' ').strip()

            blob = TextBlob(text_data)
            sentiment_scores = []

            for sentence in blob.sentences:
                # Filtere leere oder zu kurze Sätze
                if len(sentence.words) < 3:
                    continue

                sentiment_scores.append(sentence.sentiment.polarity)

            if not sentiment_scores:
                logger.warning("Keine verwertbaren Sätze für Sentiment-Analyse gefunden")
                return {'score': 0.5, 'confidence': 0}

            avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
            normalized_score = (avg_sentiment + 1) / 2  # Konvertiert von [-1,1] zu [0,1]

            return {
                'score': normalized_score,
                'confidence': min(len(sentiment_scores) / 10, 1),  # Konfidenz basierend auf Datenmenge
                'metrics': {
                    'sample_size': len(sentiment_scores),
                    'raw_sentiment': avg_sentiment,
                    'sentiment_distribution': {
                        'positive': sum(1 for s in sentiment_scores if s > 0.1),
                        'neutral': sum(1 for s in sentiment_scores if -0.1 <= s <= 0.1),
                        'negative': sum(1 for s in sentiment_scores if s < -0.1)
                    }
                }
            }

        except Exception as e:
            logger.error(f"Fehler bei der Social Media Sentiment-Analyse: {e}")
            return {'score': 0.5, 'confidence': 0}

    def _analyze_dex_sentiment(self, data: Dict[str, Any]) -> Dict[str, Any]:
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