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
        dates = pd.date_range(start='2025-01-01', end='2025-03-06', freq='H')
        test_data = pd.DataFrame({
            'close': range(len(dates)),
            'volume': [1000000] * len(dates),
            'timestamp': dates
        })
        logger.info(f"Test-Daten erstellt mit {len(dates)} Datenpunkten")

        # Teste Vorhersage
        prediction = await engine.predict_next_move(test_data)
        
        logger.info("\nVorhersage-Ergebnisse:")
        logger.info(f"Preisvorhersage: {prediction['prediction']:.2f}")
        logger.info(f"Konfidenz: {prediction['confidence']:.2f}")
        logger.info(f"Signal: {prediction['signal']}")
        logger.info(f"Sentiment Score: {prediction['sentiment']['overall_score']:.2f}")

        # Teste Sentiment-Analyse separat
        sentiment = await engine.sentiment_analyzer.analyze_market_sentiment()
        
        logger.info("\nSentiment-Analyse:")
        logger.info(f"Gesamt-Score: {sentiment['overall_score']:.2f}")
        for source, data in sentiment['sources'].items():
            logger.info(f"{source}: Score {data['score']:.2f}, "
                     f"Konfidenz {data['confidence']:.2f}")

    except Exception as e:
        logger.error(f"Fehler beim Testen: {e}")

if __name__ == "__main__":
    asyncio.run(test_ai_trading())
