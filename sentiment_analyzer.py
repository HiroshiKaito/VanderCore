import logging
from textblob import TextBlob
from nltk.sentiment.vader import SentimentIntensityAnalyzer
import nltk
import requests
from datetime import datetime, timedelta
import json
from typing import Dict, Any, Optional
import asyncio

logger = logging.getLogger(__name__)

class SentimentAnalyzer:
    def __init__(self):
        """Initialisiert den Sentiment Analyzer"""
        try:
            # Stelle sicher, dass VADER Lexikon geladen ist
            try:
                nltk.data.find('sentiment/vader_lexicon.zip')
            except LookupError:
                nltk.download('vader_lexicon')

            self.vader = SentimentIntensityAnalyzer()
        except Exception as e:
            logger.error(f"Fehler beim Laden von VADER: {e}")
            self.vader = None

        # API Endpoints mit Backup-URLs
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.dex_screener_api = "https://api.dexscreener.com/latest/dex"

        # Nitter Instanzen für Failover
        self.nitter_instances = [
            "https://nitter.net",
            "https://nitter.cz",
            "https://nitter.ca",
            "https://nitter.it"
        ]

        # API Konfiguration
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; SolanaBot/1.0)',
            'Accept': 'application/json'
        }

        # Retry Konfiguration
        self.max_retries = 3
        self.retry_delay = 2
        self.timeout = 15

    def _analyze_text_sentiment(self, text: str) -> Dict[str, float]:
        """Analysiert Text-Sentiment mit VADER und TextBlob"""
        try:
            # VADER Analyse
            if self.vader:
                vader_scores = self.vader.polarity_scores(text)
                vader_compound = vader_scores['compound']
            else:
                vader_compound = 0

            # TextBlob Analyse
            blob = TextBlob(text)
            textblob_score = blob.sentiment.polarity

            # Kombiniere die Scores
            combined_score = (vader_compound + textblob_score) / 2 if self.vader else textblob_score
            normalized_score = (combined_score + 1) / 2  # Konvertiere zu [0,1]

            return {
                'score': normalized_score,
                'confidence': min(abs(vader_compound - textblob_score), 1) if self.vader else 0.5
            }

        except Exception as e:
            logger.error(f"Fehler bei der Text-Sentiment-Analyse: {e}")
            return {'score': 0.5, 'confidence': 0}

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
        """Generische Fetch-Funktion mit verbessertem Retry-Mechanismus"""
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

                if response.status_code == 404:
                    logger.warning(f"Endpoint nicht gefunden: {url}")
                    return None

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
        """Holt Solana-Daten von CoinGecko mit verbesserter Fehlerbehandlung"""
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

    async def _fetch_dex_data(self) -> Dict[str, Any]:
        """Holt DEX-Daten für Solana mit verbesserter Fehlerbehandlung"""
        try:
            # Korrekte Solana Token Adresse
            sol_token_address = "So11111111111111111111111111111111111111112"

            # Versuche zuerst die Token-spezifische API
            response = await self._fetch_with_retry(
                f"{self.dex_screener_api}/tokens/{sol_token_address}"
            )

            if response and response.status_code == 200:
                data = response.json()
                if 'pairs' in data:
                    logger.info("DEX Daten erfolgreich abgerufen")
                    return data

            # Fallback: Versuche die Top-Pairs API
            response = await self._fetch_with_retry(
                f"{self.dex_screener_api}/pairs/solana"
            )

            if response and response.status_code == 200:
                data = response.json()
                if 'pairs' in data:
                    # Filtere nach SOL/USDC Paaren
                    sol_pairs = [
                        pair for pair in data['pairs']
                        if (pair.get('baseToken', {}).get('symbol', '').upper() == 'SOL' and
                            pair.get('quoteToken', {}).get('symbol', '').upper() == 'USDC')
                    ]

                    if sol_pairs:
                        logger.info("SOL/USDC Pairs gefunden")
                        return {'pairs': sol_pairs}

            logger.warning("Keine SOL/USDC Paare gefunden")
            return {'pairs': []}

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der DEX-Daten: {e}")
            return {'pairs': []}

    async def _fetch_social_data(self) -> str:
        """Holt Social Media Daten mit Fallback-Mechanismen"""
        try:
            for instance in self.nitter_instances:
                response = await self._fetch_with_retry(
                    f"{instance}/search",
                    params={
                        'f': 'tweets',
                        'q': 'solana language:de OR language:en',
                        'since': '24h'
                    }
                )

                if response and response.status_code == 200:
                    logger.info("Social Media Daten erfolgreich abgerufen")
                    return response.text

            logger.warning("Keine Nitter Instanz verfügbar")
            return ""

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Social Media Daten: {e}")
            return ""

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
        """Analysiert Social Media Text mit VADER und TextBlob"""
        try:
            if not text_data:
                return {'score': 0.5, 'confidence': 0}

            # Bereinige Text und bereite ihn für die Analyse vor
            text_data = ' '.join(text_data.split())  # Normalisiere Whitespace
            text_data = text_data.replace('\n', ' ').strip()

            return self._analyze_text_sentiment(text_data)

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