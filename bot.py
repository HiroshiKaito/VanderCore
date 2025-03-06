import logging
import os
from datetime import datetime
import threading
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackQueryHandler,
    MessageHandler, Filters, CallbackContext
)
from config import Config

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
        self.config = Config()
        self.active_users = set()
        self.is_running = False
        self.updater = None
        logger.info("Bot initialisiert")

    def start(self):
        """Startet den Bot"""
        try:
            logger.info("Starte Bot...")
            self.updater = Updater(self.config.TELEGRAM_TOKEN, use_context=True)
            dp = self.updater.dispatcher

            # Registriere Handler
            dp.add_handler(CommandHandler('start', self.start_command))
            dp.add_handler(CommandHandler('hilfe', self.help_command))

            # Starte Polling ohne Signal-Handler
            self.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot erfolgreich gestartet!")

            self.is_running = True
            return True

        except Exception as e:
            logger.error(f"Fehler beim Starten des Bots: {e}", exc_info=True)
            self.is_running = False
            return False

    def stop(self):
        """Stoppt den Bot"""
        try:
            if self.updater:
                self.updater.stop()
            self.is_running = False
            logger.info("Bot gestoppt")
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Bots: {e}")

    def start_command(self, update: Update, context: CallbackContext):
        """Start-Befehl Handler"""
        try:
            user_id = str(update.effective_user.id)
            logger.info(f"Start-Befehl von User {user_id}")

            self.active_users.add(user_id)

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
                "📚 Verfügbare Befehle:\n"
                "/start - Bot starten\n"
                "/hilfe - Diese Hilfe anzeigen"
            )
        except Exception as e:
            logger.error(f"Fehler beim Hilfe-Befehl: {e}")

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