import logging
from dex_connector import DexConnector
from chart_analyzer import ChartAnalyzer
from datetime import datetime
import time

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_market_data():
    dex = DexConnector()
    analyzer = ChartAnalyzer()
    
    logger.info("Starting market data test...")
    
    # Test 5 price updates
    for i in range(5):
        try:
            # Get market data
            market_info = dex.get_market_info("So11111111111111111111111111111111111111112")
            if market_info and market_info.get('price', 0) > 0:
                logger.info(f"[{i+1}/5] Fetched SOL price: {market_info['price']:.2f} USDC")
                
                # Update chart data
                analyzer.update_price_data(dex, "SOL")
                
                # Analyze trend
                trend = analyzer.analyze_trend()
                logger.info(f"Trend Analysis: {trend}")
                
                # Get support/resistance
                levels = analyzer.get_support_resistance()
                logger.info(f"Support/Resistance: {levels}")
            else:
                logger.error("Failed to get valid market data")
                
        except Exception as e:
            logger.error(f"Error in test iteration {i+1}: {e}")
            
        time.sleep(5)  # Wait 5 seconds between updates
        
    logger.info("Market data test completed")

if __name__ == "__main__":
    test_market_data()
