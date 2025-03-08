"""Webhook-basierter Telegram Bot mit Flask"""
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, Dispatcher
from config import config
import os
import json
import atexit
import sys

# Logging-Konfiguration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("webhook_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask App
app = Flask(__name__)

# Telegram Bot
updater = None
dispatcher = None

def setup_webhook(url):
    """Webhook-Setup"""
    try:
        # Validiere URL
        if not url.startswith(('http://', 'https://')):
            logger.error(f"Ungültige Webhook-URL: {url}")
            return False

        # Setze Webhook
        webhook_result = updater.bot.set_webhook(url)
        if not webhook_result:
            logger.error(f"Webhook-Setup fehlgeschlagen für URL: {url}")
            return False

        logger.info(f"Webhook erfolgreich gesetzt auf: {url}")
        return True

    except Exception as e:
        logger.error(f"Fehler beim Webhook-Setup: {e}")
        return False

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    update.message.reply_text(
        "👋 Willkommen beim Trading Bot!\n"
        "Ich bin bereit für deine Befehle."
    )

@app.route('/telegram-webhook', methods=['POST'])
def webhook_handler():
    """Handler für eingehende Webhook-Updates"""
    try:
        # Verarbeite Update
        json_data = request.get_json()
        update = Update.de_json(json_data, updater.bot)
        dispatcher.process_update(update)
        return "OK"
    except Exception as e:
        logger.error(f"Fehler bei Webhook-Verarbeitung: {e}")
        return "Error", 500

def initialize_bot():
    """Initialisiere den Bot"""
    global updater, dispatcher

    try:
        # Erstelle Updater
        updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
        dispatcher = updater.dispatcher

        # Registriere Handler
        dispatcher.add_handler(CommandHandler("start", start))

        # Weitere Handler hier...

        logger.info("Bot erfolgreich initialisiert")
        return True
    except Exception as e:
        logger.error(f"Fehler bei Bot-Initialisierung: {e}")
        return False

def main():
    """Hauptfunktion"""
    try:
        # Initialisiere Bot
        if not initialize_bot():
            return

        # Setup Webhook mit externer URL
        webhook_url = os.environ.get('WEBHOOK_URL')
        if not webhook_url:
            logger.error("Keine WEBHOOK_URL konfiguriert")
            return

        if not setup_webhook(webhook_url):
            return

        logger.info("Starte Flask Server...")
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,  # Deaktiviere Debug-Modus für Produktion
            use_reloader=False,  # Verhindert doppeltes Starten
            threaded=True  # Aktiviere Threading für bessere Performance
        )

    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}")
        raise

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot wird durch Benutzer beendet")
    except Exception as e:
        logger.error(f"=== Kritischer Fehler beim Starten des Bots: {e} ===")
        sys.exit(1)