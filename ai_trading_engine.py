import logging
import numpy as np
from typing import Dict, List, Tuple, Any
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
from sklearn.ensemble import RandomForestRegressor
import ta
import requests
from datetime import datetime, timedelta
import asyncio

logger = logging.getLogger(__name__)

class AITradingEngine:
    def __init__(self):
        """Initialisiert die KI-Trading-Engine"""
        self.model = None
        self.scaler = MinMaxScaler()
        self.cached_data = {}
        self.last_prediction = None
        self.confidence_threshold = 0.75

        # API Endpoints
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        self.dex_screener_api = "https://api.dexscreener.com/latest"  # Korrigierter Base-URL
        self.nitter_api = "https://nitter.cz/search"  # Alternative Nitter Instance mit SSL
        self.solana_rpc = "https://api.mainnet-beta.solana.com"

        # Token Addresses
        self.sol_token_address = "So11111111111111111111111111111111111111112"  # Wrapped SOL token address

        logger.info("KI-Trading-Engine initialisiert mit scikit-learn")

    def _init_model(self):
        """Initialisiert das ML-Modell"""
        self.model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )

    def prepare_features(self, price_data: pd.DataFrame) -> np.ndarray:
        """Bereitet Features für das ML-Modell vor"""
        try:
            df = price_data.copy()

            # Technische Indikatoren
            df['rsi'] = ta.momentum.rsi(df['close'], window=14)
            macd = ta.trend.macd(df['close'])
            df['macd'] = macd.iloc[:, 0]
            bb = ta.volatility.BollingerBands(df['close'])
            df['bb_upper'] = bb.bollinger_hband()
            df['bb_lower'] = bb.bollinger_lband()
            df['volume_sma'] = ta.trend.sma_indicator(df['volume'], window=20)

            # Preisbewegungen
            df['price_change'] = df['close'].pct_change()
            df['volatility'] = df['close'].rolling(window=20).std()
            df['volume_change'] = df['volume'].pct_change()
            df['trend_strength'] = abs(df['price_change'].rolling(window=10).mean())

            feature_columns = [
                'close', 'volume', 'rsi', 'macd', 'bb_upper', 'bb_lower',
                'price_change', 'volatility', 'volume_change', 'trend_strength'
            ]

            # Entferne NaN-Werte
            df = df.fillna(method='ffill').fillna(method='bfill')

            return self.scaler.fit_transform(df[feature_columns])

        except Exception as e:
            logger.error(f"Fehler bei der Feature-Vorbereitung: {e}")
            return np.array([])

    def _build_model(self):
        """Erstellt das Random Forest Modell"""
        try:
            self._init_model()
            logger.info("Random Forest Modell erfolgreich erstellt")

        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Models: {e}")
            self.model = None

    def predict_next_move(self, current_data: pd.DataFrame) -> Dict[str, Any]:
        """Sagt die nächste Kursbewegung vorher"""
        try:
            if self.model is None:
                self._build_model()
                return self._predict_with_technical_analysis(current_data)

            X = self.prepare_features(current_data)
            if len(X) == 0:
                return {'prediction': None, 'confidence': 0, 'signal': 'neutral'}

            # Verwende die letzten Datenpunkte für die Vorhersage
            prediction = self.model.predict(X[-1:])
            current_price = current_data['close'].iloc[-1]
            predicted_price = self.scaler.inverse_transform(prediction.reshape(-1, 1))[0][0]

            price_change = (predicted_price - current_price) / current_price * 100
            volatility = current_data['close'].rolling(window=20).std().iloc[-1]
            volume_trend = current_data['volume'].pct_change().rolling(window=5).mean().iloc[-1]

            confidence = self._calculate_confidence(
                price_change=price_change,
                volatility=volatility,
                volume_trend=volume_trend,
                current_price=current_price
            )

            return {
                'prediction': predicted_price,
                'confidence': confidence,
                'price_change': price_change,
                'signal': 'long' if price_change > 0 else 'short',
                'volatility': volatility,
                'volume_trend': volume_trend,
                'timestamp': pd.Timestamp.now().timestamp()
            }

        except Exception as e:
            logger.error(f"Fehler bei der Vorhersage: {e}")
            return self._predict_with_technical_analysis(current_data)

    def _predict_with_technical_analysis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Fallback-Vorhersage basierend auf technischer Analyse"""
        try:
            rsi = ta.momentum.rsi(data['close'], window=14).iloc[-1]
            macd = ta.trend.macd(data['close']).iloc[-1, 0]

            price = data['close'].iloc[-1]
            price_change = data['close'].pct_change().iloc[-1] * 100
            volume_change = data['volume'].pct_change().iloc[-1] * 100

            signal = 'neutral'
            confidence = 0.5

            if rsi < 30:  # Überverkauft
                signal = 'long'
                confidence = min(0.7, confidence + 0.2)
            elif rsi > 70:  # Überkauft
                signal = 'short'
                confidence = min(0.7, confidence + 0.2)

            if macd > 0 and volume_change > 0:
                confidence = min(0.8, confidence + 0.1)
            elif macd < 0 and volume_change < 0:
                confidence = min(0.8, confidence + 0.1)

            return {
                'prediction': None,
                'confidence': confidence,
                'signal': signal,
                'price_change': price_change,
                'volatility': data['close'].std(),
                'volume_trend': volume_change,
                'timestamp': pd.Timestamp.now().timestamp()
            }

        except Exception as e:
            logger.error(f"Fehler bei der technischen Analyse: {e}")
            return {'prediction': None, 'confidence': 0, 'signal': 'neutral'}

    def _calculate_confidence(self, price_change: float, volatility: float, 
                          volume_trend: float, current_price: float) -> float:
        """Berechnet die Konfidenz der Vorhersage"""
        try:
            price_confidence = min(abs(price_change) / 2, 1.0)
            volume_confidence = min(abs(volume_trend) * 5, 1.0)
            volatility_confidence = max(1 - (volatility / current_price) * 100, 0.0)

            confidence = (
                price_confidence * 0.5 +
                volume_confidence * 0.3 +
                volatility_confidence * 0.2
            )

            return min(confidence, 1.0)

        except Exception as e:
            logger.error(f"Fehler bei der Konfidenzberechnung: {e}")
            return 0.0

    def train_model(self, training_data: pd.DataFrame):
        """Trainiert das Random Forest Modell"""
        if self.model is None:
            self._build_model()

        try:
            X = self.prepare_features(training_data[:-1])  # Alle außer dem letzten Datenpunkt
            y = training_data['close'].iloc[1:].values  # Verschiebe um einen Zeitschritt

            if len(X) == 0 or len(y) == 0:
                logger.error("Keine Trainingsdaten verfügbar")
                return

            self.model.fit(X, y)
            logger.info("Modell erfolgreich trainiert")

        except Exception as e:
            logger.error(f"Fehler beim Training: {e}")

    async def fetch_market_data(self) -> Dict[str, Any]:
        """Holt erweiterte Marktdaten von verschiedenen Quellen"""
        try:
            data = {}
            headers = {
                'User-Agent': 'Mozilla/5.0 (compatible; SolanaBot/1.0)',
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            }

            # CoinGecko Daten mit Rate Limiting und Retry
            try:
                coingecko_url = f"{self.coingecko_api}/simple/price"
                params = {
                    'ids': 'solana',
                    'vs_currencies': 'usd',
                    'include_24hr_vol': True,
                    'include_24hr_change': True
                }
                response = requests.get(coingecko_url, params=params, headers=headers, timeout=10)
                if response.status_code == 200:
                    data['coingecko'] = response.json()
                    logger.info("CoinGecko Daten erfolgreich abgerufen")
                else:
                    logger.warning(f"CoinGecko API Fehler: {response.status_code}")
            except Exception as e:
                logger.error(f"CoinGecko API Fehler: {e}")

            # DEX Screener Daten
            try:
                # Versuche zuerst den Token-spezifischen Endpoint
                logger.info(f"Versuche Token-spezifischen DEX Screener API Aufruf für SOL")
                token_url = f"{self.dex_screener_api}/pairs/solana/{self.sol_token_address}"

                response = requests.get(token_url, headers=headers, timeout=15)
                response_text = response.text if response.status_code != 200 else "OK"
                logger.info(f"DEX Screener Response Status: {response.status_code}, Response: {response_text}")

                if response.status_code == 200:
                    token_data = response.json()
                    if 'pairs' in token_data:
                        # Filter für USDC Paare
                        usdc_pairs = [
                            pair for pair in token_data['pairs']
                            if pair.get('quoteToken', {}).get('symbol', '').upper() == 'USDC'
                        ]

                        if usdc_pairs:
                            # Sortiere nach Volumen
                            usdc_pairs.sort(key=lambda x: float(x.get('volume', {}).get('h24', 0)), reverse=True)
                            best_pair = usdc_pairs[0]

                            data['dex_screener'] = {
                                'pair': best_pair,
                                'price': float(best_pair.get('priceUsd', 0)),
                                'volume24h': float(best_pair.get('volume', {}).get('h24', 0)),
                                'timestamp': datetime.now().isoformat()
                            }
                            logger.info(f"DEX Screener: SOL/USDC Pair gefunden - "
                                      f"Preis: ${data['dex_screener']['price']:.2f}, "
                                      f"24h Volume: ${data['dex_screener']['volume24h']:,.2f}")
                            return data

                # Wenn der erste Versuch fehlschlägt, versuche den trending pairs endpoint
                logger.info("Versuche trending pairs endpoint als Fallback")
                pairs_url = f"{self.dex_screener_api}/pairs/trending"
                response = requests.get(pairs_url, headers=headers, timeout=15)

                if response.status_code == 200:
                    pairs_data = response.json()
                    if 'pairs' in pairs_data:
                        sol_pairs = [
                            pair for pair in pairs_data['pairs']
                            if (pair.get('baseToken', {}).get('symbol', '').upper() == 'SOL' or
                                pair.get('baseToken', {}).get('address', '').lower() == self.sol_token_address.lower())
                            and pair.get('quoteToken', {}).get('symbol', '').upper() == 'USDC'
                            and pair.get('chainId') == 'solana'
                        ]

                        if sol_pairs:
                            best_pair = max(sol_pairs, key=lambda x: float(x.get('volume', {}).get('h24', 0)))
                            data['dex_screener'] = {
                                'pair': best_pair,
                                'price': float(best_pair.get('priceUsd', 0)),
                                'volume24h': float(best_pair.get('volume', {}).get('h24', 0)),
                                'timestamp': datetime.now().isoformat()
                            }
                            logger.info(f"DEX Screener (Trending): SOL/USDC Pair gefunden - "
                                      f"Preis: ${data['dex_screener']['price']:.2f}, "
                                      f"24h Volume: ${data['dex_screener']['volume24h']:,.2f}")
                        else:
                            logger.warning("Keine SOL/USDC Paare in trending pairs gefunden")
                            data['dex_screener'] = await self._get_solana_rpc_fallback()
                    else:
                        logger.warning("Unerwartetes Response Format von trending pairs")
                        data['dex_screener'] = await self._get_solana_rpc_fallback()
                else:
                    logger.warning(f"Beide DEX Screener Endpoints fehlgeschlagen")
                    data['dex_screener'] = await self._get_solana_rpc_fallback()

            except Exception as e:
                logger.error(f"DEX Screener API Fehler: {e}")
                data['dex_screener'] = await self._get_solana_rpc_fallback()

            # Nitter (Twitter Alternative) Sentiment
            try:
                nitter_params = {
                    'f': 'tweets',
                    'q': 'solana language:de OR language:en',
                    'since': '12h'  # Reduziert auf 12h für bessere Performance
                }
                retry_count = 0
                max_retries = 3

                while retry_count < max_retries:
                    try:
                        response = requests.get(
                            self.nitter_api,
                            params=nitter_params,
                            headers=headers,
                            timeout=20,  # Erhöhtes Timeout
                        )
                        if response.status_code == 200:
                            data['nitter'] = {
                                'text': response.text,
                                'timestamp': datetime.now().isoformat()
                            }
                            logger.info("Nitter Daten erfolgreich abgerufen")
                            break
                        elif response.status_code == 429:  # Rate Limit
                            retry_count += 1
                            if retry_count < max_retries:
                                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                                continue
                            logger.warning("Nitter Rate Limit erreicht nach allen Versuchen")
                            break
                        else:
                            logger.warning(f"Nitter API Fehler: {response.status_code}")
                            if retry_count < max_retries - 1:
                                retry_count += 1
                                await asyncio.sleep(2 ** retry_count)
                                continue
                            break
                    except requests.exceptions.RequestException as e:
                        logger.error(f"Nitter Request Fehler: {e}")
                        if retry_count < max_retries - 1:
                            retry_count += 1
                            await asyncio.sleep(2 ** retry_count)
                            continue
                        break

            except Exception as e:
                logger.error(f"Nitter API Fehler: {e}")

            if not data:
                logger.warning("Keine Marktdaten konnten abgerufen werden")
            else:
                logger.info(f"Marktdaten erfolgreich abgerufen von: {', '.join(data.keys())}")

            return data

        except Exception as e:
            logger.error(f"Genereller Fehler beim Abrufen der Marktdaten: {e}")
            return {}

    async def _get_solana_rpc_fallback(self) -> Dict[str, Any]:
        """Fallback für DEX Screener mit Solana RPC"""
        try:
            rpc_payload = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getRecentBlockhash"
            }
            response = requests.post(self.solana_rpc, json=rpc_payload)
            if response.status_code == 200:
                logger.info("Solana RPC Fallback erfolgreich")
                return response.json()
            logger.warning(f"Solana RPC Fallback fehlgeschlagen: {response.status_code}")
            return {}
        except Exception as e:
            logger.error(f"Solana RPC Fallback Fehler: {e}")
            return {}

    def backtest_strategy(self, historical_data: pd.DataFrame) -> Dict[str, float]:
        """Führt erweitertes Backtesting der Strategie durch"""
        try:
            results = {
                'total_trades': 0,
                'winning_trades': 0,
                'losing_trades': 0,
                'total_profit': 0.0,
                'max_drawdown': 0.0,
                'sharpe_ratio': 0.0,
                'win_rate': 0.0,
                'avg_profit': 0.0,
                'avg_loss': 0.0
            }

            # Implementiere erweiterte Backtesting-Logik
            profits = []
            current_drawdown = 0
            max_drawdown = 0

            for i in range(len(historical_data) - 60):
                prediction = self.predict_next_move(historical_data.iloc[:i+60])
                if prediction['confidence'] > self.confidence_threshold:
                    # Simuliere Trade
                    entry_price = historical_data['close'].iloc[i+59]
                    exit_price = historical_data['close'].iloc[i+60]
                    profit = (exit_price - entry_price) / entry_price * 100

                    profits.append(profit)
                    results['total_trades'] += 1

                    if profit > 0:
                        results['winning_trades'] += 1
                        results['avg_profit'] = (results['avg_profit'] * (results['winning_trades'] - 1) + profit) / results['winning_trades'] if results['winning_trades'] > 1 else profit
                    else:
                        results['losing_trades'] += 1
                        results['avg_loss'] = (results['avg_loss'] * (results['losing_trades'] - 1) + profit) / results['losing_trades'] if results['losing_trades'] > 1 else profit

                    # Berechne Drawdown
                    current_drawdown += profit
                    max_drawdown = min(max_drawdown, current_drawdown)

            # Berechne finale Metriken
            results['total_profit'] = sum(profits)
            results['max_drawdown'] = abs(max_drawdown)
            results['win_rate'] = results['winning_trades'] / results['total_trades'] if results['total_trades'] > 0 else 0

            # Berechne Sharpe Ratio (assuming daily returns)
            if len(profits) > 0:
                returns = pd.Series(profits)
                results['sharpe_ratio'] = returns.mean() / returns.std() if returns.std() != 0 else 0

            logger.info(f"Backtesting-Ergebnisse: {results}")
            return results

        except Exception as e:
            logger.error(f"Fehler beim Backtesting: {e}")
            return {}