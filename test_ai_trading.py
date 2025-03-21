import asyncio
import logging
import pandas as pd
from datetime import datetime, timedelta
from ai_trading_engine import AITradingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_ai_trading():
    """Test die erweiterte AI Trading Engine"""
    try:
        # Initialisiere AI Trading Engine
        engine = AITradingEngine()
        logger.info("AI Trading Engine initialisiert")

        # Erstelle Test-Daten
        dates = pd.date_range(start='2025-01-01', end='2025-03-06', freq='h')
        test_data = pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(len(dates))],
            'high': [100 + i * 0.15 for i in range(len(dates))],
            'low': [100 + i * 0.05 for i in range(len(dates))],
            'close': [100 + i * 0.1 for i in range(len(dates))],  # Aufsteigender Trend
            'volume': [1000000 + i * 1000 for i in range(len(dates))],  # Steigendes Volumen
            'timestamp': dates
        })
        logger.info(f"Test-Daten erstellt mit {len(dates)} Datenpunkten")

        # Teste Feature-Extraktion
        features = engine.prepare_features(test_data)
        logger.info(f"Feature Shape: {features.shape}")

        # Teste Vorhersage
        prediction = await engine.predict_next_move(test_data)

        if prediction and 'prediction' in prediction:
            logger.info("\nVorhersage-Ergebnisse:")
            logger.info(f"Preisvorhersage: {prediction.get('prediction', 'N/A')}")
            logger.info(f"Konfidenz: {prediction.get('confidence', 0):.2f}")
            logger.info(f"Signal: {prediction.get('signal', 'neutral')}")
            logger.info(f"Sentiment Score: {prediction.get('sentiment', {}).get('overall_score', 0):.2f}")

            # Teste Sentiment-Analyse separat
            sentiment = await engine.sentiment_analyzer.analyze_market_sentiment()

            logger.info("\nSentiment-Analyse:")
            logger.info(f"Gesamt-Score: {sentiment.get('overall_score', 0):.2f}")
            for source, data in sentiment.get('sources', {}).items():
                if isinstance(data, dict):
                    logger.info(f"{source}: Score {data.get('score', 0):.2f}, "
                            f"Konfidenz {data.get('confidence', 0):.2f}")

            # Teste Risikomanagement
            risk_info = prediction.get('risk_management', {})
            logger.info("\nRisikomanagement:")
            logger.info(f"Position Size: {risk_info.get('position_size', 0):.2f}")
            logger.info(f"Stoploss: {risk_info.get('stoploss', 0):.2f}")
            logger.info(f"Takeprofit: {risk_info.get('takeprofit', 0):.2f}")
        else:
            logger.warning("Keine gültige Vorhersage erhalten")

    except Exception as e:
        logger.error(f"Fehler beim Testen: {e}")


async def test_model_training():
    """Test des Modelltrainings und der Vorhersagequalität"""
    try:
        engine = AITradingEngine()

        # Erstelle Trainingsdaten mit klarem Trend
        dates = pd.date_range(start='2025-01-01', end='2025-01-10', freq='h')
        train_data = pd.DataFrame({
            'open': [100 + i * 0.1 for i in range(len(dates))],
            'high': [100 + i * 0.15 for i in range(len(dates))],
            'low': [100 + i * 0.05 for i in range(len(dates))],
            'close': [100 + i * 0.1 for i in range(len(dates))],
            'volume': [1000000 + i * 1000 for i in range(len(dates))],
            'sentiment_score': [0.6 + (i % 5) * 0.1 for i in range(len(dates))],
            'timestamp': dates
        })

        # Trainiere Modell
        engine.train_model(train_data)

        # Teste Vorhersage auf Testdaten
        test_dates = pd.date_range(start='2025-01-11', end='2025-01-12', freq='h')
        test_data = pd.DataFrame({
            'open': [110 + i * 0.1 for i in range(len(test_dates))],
            'high': [110 + i * 0.15 for i in range(len(test_dates))],
            'low': [110 + i * 0.05 for i in range(len(test_dates))],
            'close': [110 + i * 0.1 for i in range(len(test_dates))],
            'volume': [1100000 + i * 1000 for i in range(len(test_dates))],
            'sentiment_score': [0.7 for _ in range(len(test_dates))],
            'timestamp': test_dates
        })

        prediction = await engine.predict_next_move(test_data)

        logger.info("\nModelltraining und Vorhersage Test:")
        logger.info(f"Trainingsdaten Shape: {train_data.shape}")
        logger.info(f"Vorhersage: {prediction.get('prediction', 'N/A')}")
        logger.info(f"Konfidenz: {prediction.get('confidence', 0):.2f}")
        logger.info(f"Signal: {prediction.get('signal', 'neutral')}")

    except Exception as e:
        logger.error(f"Fehler beim Modelltraining Test: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_trading())
    asyncio.run(test_model_training())