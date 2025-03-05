from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import time
from datetime import datetime, timedelta
from chart_analyzer import ChartAnalyzer
from dex_connector import DexConnector
from signal_processor import SignalProcessor

app = Flask(__name__)
socketio = SocketIO(app)

# Initialize components
dex_connector = DexConnector()
chart_analyzer = ChartAnalyzer()
signal_processor = SignalProcessor()

@app.route('/dashboard')
def dashboard():
    """Rendert das Trading Dashboard"""
    return render_template('dashboard.html')

def emit_market_data():
    """Sendet Marktdaten über WebSocket"""
    while True:
        try:
            # Hole aktuelle Marktdaten
            market_info = dex_connector.get_market_info("SOL")
            if market_info and market_info.get('price', 0) > 0:
                # Aktualisiere Chart Analyzer
                chart_analyzer.update_price_data(dex_connector, "SOL")
                trend_analysis = chart_analyzer.analyze_trend()

                # Berechne 24h Änderung
                data_24h = chart_analyzer.data
                if len(data_24h) > 1:
                    old_price = data_24h['price'].iloc[0]
                    current_price = market_info['price']
                    change_24h = ((current_price - old_price) / old_price) * 100
                else:
                    change_24h = 0

                # Sende Update an Clients
                socketio.emit('market_update', {
                    'price': market_info['price'],
                    'trend': trend_analysis.get('trend', 'neutral'),
                    'strength': trend_analysis.get('stärke', 0),
                    'change_24h': change_24h
                })

                # Verarbeite potenzielle Trading Signale
                signal = signal_processor.process_signal({
                    'pair': 'SOL/USDC',
                    'price': market_info['price'],
                    'dex_connector': dex_connector,
                    'token_address': "SOL"
                })

                if signal:
                    socketio.emit('trading_signal', signal)

        except Exception as e:
            print(f"Fehler beim Market Data Update: {e}")

        time.sleep(3)  # Update alle 3 Sekunden

def run_dashboard():
    """Startet das Dashboard"""
    # Starte den Market Data Thread
    market_thread = threading.Thread(target=emit_market_data)
    market_thread.daemon = True
    market_thread.start()

    # Starte den Flask-SocketIO Server
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False, log_output=True)

if __name__ == '__main__':
    run_dashboard()