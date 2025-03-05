import logging
import numpy as np
from typing import Dict, List, Tuple, Any
import pandas as pd
from sklearn.preprocessing import MinMaxScaler
import pandas_ta as ta

# Importiere TensorFlow mit Error Handling
try:
    import tensorflow as tf
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
    from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
    TF_AVAILABLE = True
except ImportError:
    TF_AVAILABLE = False
    logging.warning("TensorFlow konnte nicht importiert werden. KI-Funktionen sind eingeschränkt.")

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
        self.dex_screener_api = "https://api.dexscreener.com/latest"
        self.reddit_api = "https://www.reddit.com/r/solana"
        self.nitter_api = "https://nitter.net/search"

        # Initialisiere TensorFlow Session wenn verfügbar
        if TF_AVAILABLE:
            self._setup_gpu()
            self._build_model()
            logger.info("KI-Trading-Engine mit TensorFlow initialisiert")
        else:
            logger.warning("KI-Trading-Engine läuft im eingeschränkten Modus ohne TensorFlow")

    def _setup_gpu(self):
        """Konfiguriert GPU-Nutzung für TensorFlow"""
        if not TF_AVAILABLE:
            return

        try:
            gpus = tf.config.list_physical_devices('GPU')
            if gpus:
                for gpu in gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                logger.info(f"GPU-Unterstützung aktiviert: {len(gpus)} GPUs gefunden")
            else:
                logger.info("Keine GPU gefunden - nutze CPU")
        except Exception as e:
            logger.warning(f"GPU Setup fehlgeschlagen: {e}")

    async def fetch_market_data(self) -> Dict[str, Any]:
        """Holt erweiterte Marktdaten von verschiedenen Quellen"""
        try:
            data = {}

            # CoinGecko Daten
            coingecko_url = f"{self.coingecko_api}/coins/solana"
            params = {
                'localization': 'false',
                'tickers': 'true',
                'market_data': 'true',
                'community_data': 'true',
                'developer_data': 'true'
            }
            response = requests.get(coingecko_url, params=params)
            if response.status_code == 200:
                data['coingecko'] = response.json()

            # DEX Screener Daten
            dex_url = f"{self.dex_screener_api}/dex/solana"
            response = requests.get(dex_url)
            if response.status_code == 200:
                data['dex_screener'] = response.json()

            # Reddit Sentiment (Simple Scraping)
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(f"{self.reddit_api}/new.json", headers=headers)
            if response.status_code == 200:
                data['reddit'] = response.json()

            # Nitter (Twitter Alternative) Sentiment
            nitter_params = {'f': 'tweets', 'q': 'solana'}
            response = requests.get(self.nitter_api, params=nitter_params)
            if response.status_code == 200:
                data['nitter'] = response.text  # HTML Response für Parsing

            logger.info("Marktdaten erfolgreich abgerufen")
            return data

        except Exception as e:
            logger.error(f"Fehler beim Abrufen der Marktdaten: {e}")
            return {}

    def predict_next_move(self, current_data: pd.DataFrame) -> Dict[str, Any]:
        """Sagt die nächste Kursbewegung vorher"""
        try:
            if not TF_AVAILABLE:
                # Fallback zur technischen Analyse wenn TensorFlow nicht verfügbar
                return self._predict_with_technical_analysis(current_data)

            # KI-basierte Vorhersage
            X = self.prepare_features(current_data)
            if len(X) == 0:
                return {'prediction': None, 'confidence': 0, 'signal': 'neutral'}

            prediction = self.model.predict(X[-1:], verbose=0)
            current_price = current_data['close'].iloc[-1]
            predicted_price = self.scaler.inverse_transform(prediction)[0][0]

            # Berechne zusätzliche Metriken
            price_change = (predicted_price - current_price) / current_price * 100
            volatility = current_data['close'].rolling(window=20).std().iloc[-1]
            volume_trend = current_data['volume'].pct_change().rolling(window=5).mean().iloc[-1]

            # Berechne Konfidenz
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
                'timestamp': datetime.now().timestamp()
            }

        except Exception as e:
            logger.error(f"Fehler bei der Vorhersage: {e}")
            return {'prediction': None, 'confidence': 0, 'signal': 'neutral'}

    def _predict_with_technical_analysis(self, data: pd.DataFrame) -> Dict[str, Any]:
        """Fallback-Vorhersage basierend auf technischer Analyse"""
        try:
            # Berechne technische Indikatoren
            rsi = ta.rsi(data['close'], length=14).iloc[-1]
            macd = ta.macd(data['close'])['MACD_12_26_9'].iloc[-1]
            bb = ta.bbands(data['close'])

            # Analysiere Marktsituation
            price = data['close'].iloc[-1]
            price_change = data['close'].pct_change().iloc[-1] * 100
            volume_change = data['volume'].pct_change().iloc[-1] * 100

            # Generiere Signal basierend auf technischer Analyse
            signal = 'neutral'
            confidence = 0.5  # Basis-Konfidenz

            if rsi < 30:  # Überverkauft
                signal = 'long'
                confidence = min(0.7, confidence + 0.2)
            elif rsi > 70:  # Überkauft
                signal = 'short'
                confidence = min(0.7, confidence + 0.2)

            if macd > 0 and volume_change > 0:  # Positiver MACD mit Volumen
                confidence = min(0.8, confidence + 0.1)
            elif macd < 0 and volume_change < 0:  # Negativer MACD mit Volumen
                confidence = min(0.8, confidence + 0.1)

            return {
                'prediction': None,  # Keine konkrete Preisvorhersage
                'confidence': confidence,
                'signal': signal,
                'price_change': price_change,
                'volatility': data['close'].std(),
                'volume_trend': volume_change,
                'timestamp': datetime.now().timestamp()
            }

        except Exception as e:
            logger.error(f"Fehler bei der technischen Analyse: {e}")
            return {'prediction': None, 'confidence': 0, 'signal': 'neutral'}

    def _calculate_confidence(self, price_change: float, volatility: float, 
                            volume_trend: float, current_price: float) -> float:
        """Berechnet die Konfidenz der Vorhersage"""
        try:
            # Normalisiere die Metriken
            price_confidence = min(abs(price_change) / 2, 1.0)
            volume_confidence = min(abs(volume_trend) * 5, 1.0)
            volatility_confidence = max(1 - (volatility / current_price) * 100, 0.0)

            # Gewichtete Konfidenz
            confidence = (
                price_confidence * 0.5 +
                volume_confidence * 0.3 +
                volatility_confidence * 0.2
            )

            return min(confidence, 1.0)

        except Exception as e:
            logger.error(f"Fehler bei der Konfidenzberechnung: {e}")
            return 0.0

    def prepare_features(self, price_data: pd.DataFrame) -> np.ndarray:
        """Bereitet Features für das ML-Modell vor"""
        if not TF_AVAILABLE:
            return np.array([])

        try:
            df = price_data.copy()

            # Technische Indikatoren
            df['rsi'] = ta.rsi(df['close'], length=14)
            df['macd'] = ta.macd(df['close'])['MACD_12_26_9']
            df['bb_upper'], df['bb_middle'], df['bb_lower'] = ta.bbands(df['close']).values
            df['volume_sma'] = ta.sma(df['volume'], length=20)

            # Erweiterte Indikatoren
            df['stoch_k'], df['stoch_d'] = ta.stoch(df['close'], df['high'], df['low'])
            df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'])
            df['adx'] = ta.adx(df['high'], df['low'], df['close'])['ADX_14']

            # Preisbewegungen
            df['price_change'] = df['close'].pct_change()
            df['volatility'] = df['close'].rolling(window=20).std()
            df['volume_change'] = df['volume'].pct_change()
            df['trend_strength'] = abs(df['price_change'].rolling(window=10).mean())

            # Feature-Normalisierung
            feature_columns = [
                'close', 'volume', 'rsi', 'macd', 'bb_upper', 'bb_lower',
                'stoch_k', 'stoch_d', 'mfi', 'adx', 'price_change', 'volatility',
                'volume_change', 'trend_strength'
            ]

            df_scaled = pd.DataFrame(
                self.scaler.fit_transform(df[feature_columns]),
                columns=feature_columns
            )

            # Erstelle Sequenzen
            sequences = []
            for i in range(len(df_scaled) - 60):
                sequences.append(df_scaled.iloc[i:i+60].values)

            return np.array(sequences)

        except Exception as e:
            logger.error(f"Fehler bei der Feature-Vorbereitung: {e}")
            return np.array([])

    def _build_model(self):
        """Erstellt das LSTM-Modell"""
        if not TF_AVAILABLE:
            return

        try:
            model = Sequential([
                LSTM(256, return_sequences=True, input_shape=(60, 14)),
                Dropout(0.3),
                LSTM(128, return_sequences=True),
                Dropout(0.3),
                LSTM(64, return_sequences=False),
                Dropout(0.3),
                Dense(64, activation='relu'),
                Dropout(0.2),
                Dense(32, activation='relu'),
                Dense(1, activation='linear')
            ])

            model.compile(
                optimizer=Adam(learning_rate=0.001),
                loss='huber',
                metrics=['mae', 'mse']
            )

            self.model = model
            logger.info("LSTM Modell erfolgreich erstellt")

        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Models: {e}")
            self.model = None

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

    def train_model(self, training_data: pd.DataFrame):
        """Trainiert das LSTM-Modell mit erweiterten Features"""
        if not TF_AVAILABLE:
            return

        try:
            X = self.prepare_features(training_data)
            y = training_data['close'].iloc[60:].values
            y_scaled = self.scaler.fit_transform(y.reshape(-1, 1))

            # Erweiterte Callbacks für besseres Training
            callbacks = [
                EarlyStopping(
                    monitor='val_loss',
                    patience=5,
                    restore_best_weights=True,
                    mode='min'
                ),
                ReduceLROnPlateau(
                    monitor='val_loss',
                    factor=0.5,
                    patience=3,
                    min_lr=0.0001
                )
            ]

            # Trainiere Modell mit erweiterter Konfiguration
            self.model.fit(
                X, y_scaled,
                epochs=100,
                batch_size=32,
                validation_split=0.2,
                callbacks=callbacks,
                shuffle=True
            )

            logger.info("Modell erfolgreich mit erweiterten Features trainiert")

        except Exception as e:
            logger.error(f"Fehler beim Training: {e}")
            raise

import requests
from datetime import datetime, timedelta