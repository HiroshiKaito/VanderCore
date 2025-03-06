import asyncio
import logging
from dex_connector import DexConnector
from chart_analyzer import ChartAnalyzer
from ai_trading_engine import AITradingEngine
from datetime import datetime
import time
import pandas as pd

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def test_market_data():
    dex = DexConnector()
    analyzer = ChartAnalyzer()
    ai_engine = AITradingEngine()

    logger.info("Starting market data and API test...")

    # Test external APIs
    try:
        market_data = await ai_engine.fetch_market_data()
        for api_name, data in market_data.items():
            if data:
                logger.info(f"{api_name} API Test: Erfolgreich")
            else:
                logger.warning(f"{api_name} API Test: Keine Daten")
    except Exception as e:
        logger.error(f"Fehler beim API Test: {e}")

    # Test DEX price updates
    for i in range(5):
        try:
            # Get market data
            market_info = dex.get_market_info("So11111111111111111111111111111111111111112")
            if market_info and market_info.get('price', 0) > 0:
                price = market_info['price']
                volume = market_info.get('volume', 0)
                timestamp = datetime.now()

                logger.info(f"[{i+1}/5] SOL Preis: {price:.2f} USDC, Volumen: {volume:.2f}")

                # Update chart data and analyze
                analyzer.update_price_data(dex, "SOL")
                trend = analyzer.analyze_trend()
                logger.info(f"Trend Analyse: {trend}")

                # Get support/resistance
                levels = analyzer.get_support_resistance()
                logger.info(f"Support/Resistance: {levels}")
            else:
                logger.error("Keine gültigen Marktdaten erhalten")

        except Exception as e:
            logger.error(f"Fehler in Test-Iteration {i+1}: {e}")

        await asyncio.sleep(5)  # Warte 5 Sekunden zwischen Updates

    logger.info("Marktdaten und API Test abgeschlossen")

if __name__ == "__main__":
    asyncio.run(test_market_data())