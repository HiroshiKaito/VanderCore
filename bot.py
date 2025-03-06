import logging
import os
import json
from datetime import datetime
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler,
    MessageHandler, Filters, CallbackContext
)
from config import Config
from automated_signal_generator import AutomatedSignalGenerator
from signal_processor import SignalProcessor
from dex_connector import DexConnector

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)

# Globale Bot-Variable
telegram_bot = None

class SolanaWalletBot:
    def __init__(self):
        """Initialisiert den Bot mit Konfiguration"""
        logger.info("Initialisiere Bot...")
        self.config = Config()
        self.active_users = set()
        self.is_running = False
        self.updater = None

        # Komponenten
        self.dex_connector = DexConnector()
        self.signal_processor = SignalProcessor()
        self.signal_generator = None

        # Lade gespeicherte User-IDs
        try:
            if os.path.exists('active_users.json'):
                with open('active_users.json', 'r') as f:
                    saved_users = json.load(f)
                    self.active_users = set(map(str, saved_users))
                    logger.info(f"Aktive Nutzer geladen: {self.active_users}")
        except Exception as e:
            logger.error(f"Fehler beim Laden der aktiven Nutzer: {e}")

    def start(self):
        """Startet den Bot"""
        try:
            logger.info("Starte Bot...")
            self.updater = Updater(self.config.TELEGRAM_TOKEN, use_context=True)
            dp = self.updater.dispatcher

            # Registriere Handler
            handlers = [
                CommandHandler('start', self.start_command),
                CommandHandler('hilfe', self.help_command),
                CommandHandler('test_signal', self.test_signal),
                CallbackQueryHandler(self.button_handler),
                MessageHandler(Filters.text & ~Filters.command, self.handle_text)
            ]

            for handler in handlers:
                dp.add_handler(handler)
                logger.info(f"Handler registriert: {handler.__class__.__name__}")

            # Starte Polling
            self.updater.start_polling(drop_pending_updates=True)
            logger.info("Telegram Bot erfolgreich gestartet!")

            # Initialisiere Signal Generator
            self.signal_generator = AutomatedSignalGenerator(
                self.dex_connector,
                self.signal_processor,
                self
            )
            self.signal_generator.start()
            logger.info("Signal Generator erfolgreich gestartet")

            self.is_running = True
            return True

        except Exception as e:
            logger.error(f"Fehler beim Starten des Bots: {e}")
            self.is_running = False
            return False

    def stop(self):
        """Stoppt den Bot"""
        try:
            if self.signal_generator:
                self.signal_generator.stop()
                logger.info("Signal Generator gestoppt")

            if self.updater:
                self.updater.stop()
                logger.info("Updater gestoppt")

            self.is_running = False
            logger.info("Bot erfolgreich gestoppt")
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Bots: {e}")

    def start_command(self, update: Update, context: CallbackContext):
        """Start-Befehl Handler"""
        try:
            user_id = str(update.effective_user.id)
            logger.info(f"Start-Befehl von User {user_id}")

            self.active_users.add(user_id)
            logger.info(f"User {user_id} zu aktiven Nutzern hinzugefügt")

            welcome_message = (
                "👋 Willkommen beim Solana Trading Bot!\n\n"
                "🚀 Ich helfe dir beim Trading mit:\n"
                "✅ Automatischen Trading-Signalen\n"
                "📊 Marktanalysen\n"
                "💰 Wallet-Verwaltung\n\n"
                "Nutze /hilfe um alle verfügbaren Befehle zu sehen."
            )

            update.message.reply_text(welcome_message)
            logger.info(f"Willkommensnachricht an User {user_id} gesendet")

        except Exception as e:
            logger.error(f"Fehler beim Start-Befehl: {e}")
            update.message.reply_text(
                "❌ Es ist ein Fehler aufgetreten. Bitte versuche es später erneut."
            )

    def help_command(self, update: Update, context: CallbackContext):
        """Hilfe-Befehl Handler"""
        try:
            update.message.reply_text(
                "📚 Verfügbare Befehle:\n\n"
                "/start - Bot starten\n"
                "/hilfe - Diese Hilfe anzeigen\n"
                "/test_signal - Test-Signal generieren"
            )
        except Exception as e:
            logger.error(f"Fehler beim Hilfe-Befehl: {e}")

    def test_signal(self, update: Update, context: CallbackContext):
        """Generiert ein Test-Signal"""
        try:
            user_id = update.effective_user.id
            logger.info(f"Test-Signal-Befehl empfangen von User {user_id}")

            # Bestätige den Empfang des Befehls
            update.message.reply_text("🔄 Generiere Test-Signal...")

            # Erstelle Test-Signal
            test_signal = {
                'pair': 'SOL/USD',
                'direction': 'long',
                'entry': 145.50,
                'stop_loss': 144.50,
                'take_profit': 147.50,
                'timestamp': datetime.now().timestamp(),
                'dex_connector': self.dex_connector,
                'token_address': "SOL",
                'expected_profit': 1.37,
                'signal_quality': 7.5,
                'trend_strength': 0.8,
            }

            # Verarbeite das Signal
            processed_signal = self.signal_processor.process_signal(test_signal)

            if processed_signal:
                signal_message = (
                    f"🎯 Trading Signal erkannt!\n\n"
                    f"Pair: {processed_signal['pair']}\n"
                    f"Position: {'📈 LONG' if processed_signal['direction'] == 'long' else '📉 SHORT'}\n"
                    f"Einstieg: {processed_signal['entry']:.2f} USD\n"
                    f"Stop Loss: {processed_signal['stop_loss']:.2f} USD\n"
                    f"Take Profit: {processed_signal['take_profit']:.2f} USD\n"
                    f"Erwarteter Profit: {processed_signal['expected_profit']:.1f}%\n"
                    f"Signal Qualität: {processed_signal['signal_quality']}/10"
                )

                keyboard = [
                    [
                        InlineKeyboardButton("✅ Handeln", callback_data="trade_signal_new"),
                        InlineKeyboardButton("❌ Ignorieren", callback_data="ignore_signal")
                    ]
                ]

                update.message.reply_text(
                    signal_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
                logger.info("Test-Signal erfolgreich gesendet")
            else:
                logger.error("Signal konnte nicht verarbeitet werden")
                update.message.reply_text("❌ Fehler bei der Signal-Verarbeitung")

        except Exception as e:
            logger.error(f"Fehler beim Generieren des Test-Signals: {e}")
            update.message.reply_text("❌ Fehler beim Generieren des Test-Signals")

    def button_handler(self, update: Update, context: CallbackContext):
        """Verarbeitet Button-Klicks"""
        query = update.callback_query
        try:
            if query.data == "trade_signal_new":
                query.answer("Signal wird verarbeitet...")
                query.message.reply_text("✅ Trading Signal wird ausgeführt!")
            elif query.data == "ignore_signal":
                query.answer("Signal ignoriert")
                query.message.delete()
        except Exception as e:
            logger.error(f"Fehler beim Button-Handler: {e}")

    def handle_text(self, update: Update, context: CallbackContext):
        """Verarbeitet Text-Nachrichten"""
        try:
            update.message.reply_text(
                "❓ Bitte nutze die verfügbaren Befehle.\n"
                "Tippe /hilfe für eine Übersicht."
            )
        except Exception as e:
            logger.error(f"Fehler bei der Textverarbeitung: {e}")

@app.route('/')
def home():
    return jsonify({
        "status": "running",
        "bot_active": bool(telegram_bot and telegram_bot.is_running),
        "timestamp": datetime.now().isoformat()
    })

@app.route('/health')
def health():
    try:
        if telegram_bot and telegram_bot.is_running:
            return jsonify({
                "status": "healthy",
                "bot_running": True,
                "active_users": len(telegram_bot.active_users),
                "timestamp": datetime.now().isoformat()
            })
        return jsonify({
            "status": "starting",
            "bot_running": False,
            "active_users": 0
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

def check_environment():
    """Überprüft die Umgebungsvariablen"""
    try:
        config = Config()
        if not config.TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN nicht gesetzt")
            return False
        if not config.ADMIN_USER_ID:
            logger.error("ADMIN_USER_ID nicht gesetzt")
            return False
        logger.info("Umgebungsvariablen erfolgreich geprüft")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Prüfen der Umgebungsvariablen: {e}")
        return False

def main():
    """Hauptfunktion zum Starten der Anwendung"""
    global telegram_bot
    try:
        logger.info("Starte Anwendung...")

        # Prüfe Umgebungsvariablen
        if not check_environment():
            logger.error("Umgebungsvariablen nicht korrekt konfiguriert")
            return

        # Erstelle und starte Bot
        telegram_bot = SolanaWalletBot()
        if not telegram_bot.start():
            logger.error("Bot konnte nicht gestartet werden")
            return

        logger.info("Bot erfolgreich gestartet")

        # Starte Flask-Server
        logger.info("Starte Flask-Server auf Port 5000...")
        app.run(
            host='0.0.0.0',
            port=5000,
            use_reloader=False,
            debug=False
        )

    except Exception as e:
        logger.error(f"Kritischer Fehler beim Starten: {e}", exc_info=True)
        if telegram_bot:
            telegram_bot.stop()

if __name__ == "__main__":
    main()