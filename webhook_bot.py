"""Webhook-basierter Telegram Bot mit Flask für Replit"""
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, Dispatcher
from config import config
import os
import json
import atexit
import sys
import requests
import threading
from time import sleep

# Logging-Konfiguration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.DEBUG,
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

def keep_alive():
    """Hält den Replit-Server am Leben"""
    while True:
        try:
            url = f"https://{os.environ.get('REPL_SLUG')}.{os.environ.get('REPL_OWNER')}.repl.co"
            requests.get(url + "/health")
            logger.debug("Keep-alive ping erfolgreich")
        except Exception as e:
            logger.warning(f"Keep-alive ping fehlgeschlagen: {e}")
        sleep(270)  # Ping alle 4.5 Minuten

def get_replit_url():
    """Generiert die Replit URL für den Webhook"""
    try:
        repl_owner = os.environ.get('REPL_OWNER')
        repl_slug = os.environ.get('REPL_SLUG')
        if not repl_owner or not repl_slug:
            logger.error("REPL_OWNER oder REPL_SLUG nicht gefunden")
            return None

        url = f"https://{repl_slug}.{repl_owner}.repl.co"
        logger.info(f"Generierte Replit URL: {url}")
        return url

    except Exception as e:
        logger.error(f"Fehler bei der URL-Generierung: {e}")
        return None

def setup_webhook():
    """Webhook-Setup mit Replit URL"""
    try:
        # Hole Replit URL
        replit_url = get_replit_url()
        if not replit_url:
            logger.error("Konnte keine Replit URL generieren")
            return False

        # Webhook URL
        webhook_url = f"{replit_url}/telegram-webhook"
        logger.info(f"Verwende Webhook URL: {webhook_url}")

        # Versuche mehrmals den Webhook zu setzen
        max_retries = 3
        retry_delay = 2  # Sekunden

        for attempt in range(max_retries):
            try:
                # Setze Webhook
                webhook_result = updater.bot.set_webhook(webhook_url)
                if webhook_result:
                    logger.info(f"Webhook erfolgreich gesetzt auf: {webhook_url}")
                    return True

                logger.warning(f"Webhook-Setup fehlgeschlagen (Versuch {attempt + 1}/{max_retries})")
                if attempt < max_retries - 1:
                    sleep(retry_delay)

            except Exception as retry_error:
                logger.error(f"Fehler beim Webhook-Setup (Versuch {attempt + 1}): {retry_error}")
                if attempt < max_retries - 1:
                    sleep(retry_delay)

        logger.error("Webhook-Setup endgültig fehlgeschlagen nach mehreren Versuchen")
        return False

    except Exception as e:
        logger.error(f"Kritischer Fehler beim Webhook-Setup: {e}")
        return False

def start_polling():
    """Startet den Bot im Polling-Modus"""
    try:
        logger.info("Wechsle zu Polling-Modus...")
        # Entferne existierenden Webhook
        updater.bot.delete_webhook()
        # Starte Polling
        updater.start_polling()
        logger.info("Polling-Modus erfolgreich gestartet")
        return True
    except Exception as e:
        logger.error(f"Fehler beim Starten des Polling-Modus: {e}")
        return False

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = update.effective_user.id
        logger.info(f"Start-Befehl von User {user_id}")

        update.message.reply_text(
            "👋 Willkommen beim Trading Bot!\n"
            "Ich bin bereit für deine Befehle."
        )
    except Exception as e:
        logger.error(f"Fehler beim Start-Command: {e}")
        update.message.reply_text("❌ Es ist ein Fehler aufgetreten")

@app.route('/health')
def health_check():
    """Health Check Endpoint"""
    try:
        # Prüfe ob der Bot noch aktiv ist
        if not updater or not updater.bot:
            return jsonify({'status': 'error', 'message': 'Bot nicht initialisiert'}), 500

        # Hole Webhook Info
        try:
            webhook_info = updater.bot.get_webhook_info()
            webhook_url = webhook_info.url
        except Exception as e:
            webhook_url = "Nicht verfügbar"
            logger.error(f"Fehler beim Abrufen der Webhook-Info: {e}")

        return jsonify({
            'status': 'healthy',
            'bot_info': {
                'username': updater.bot.username,
                'webhook_url': webhook_url
            },
            'uptime': 'active'
        })
    except Exception as e:
        logger.error(f"Health Check fehlgeschlagen: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/telegram-webhook', methods=['POST'])
def webhook_handler():
    """Handler für eingehende Webhook-Updates"""
    try:
        # Verarbeite Update
        json_data = request.get_json()
        update = Update.de_json(json_data, updater.bot)

        if update:
            dispatcher.process_update(update)
            return "OK"
        else:
            logger.warning("Ungültiges Update empfangen")
            return "Invalid Update", 400

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

        # Versuche Webhook-Setup
        webhook_success = setup_webhook()

        if webhook_success:
            # Starte Keep-Alive Thread
            keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
            keep_alive_thread.start()
            logger.info("Keep-Alive Thread gestartet")

            # Starte Flask Server im Hauptthread
            logger.info("Starte Flask Server im Hauptthread...")
            app.run(
                host='0.0.0.0',
                port=5000,
                debug=False,
                use_reloader=False
            )
        else:
            # Fallback auf Polling-Modus
            logger.info("Webhook-Setup fehlgeschlagen, verwende Polling-Modus...")
            if not start_polling():
                logger.error("Konnte weder Webhook noch Polling starten")
                return

        logger.info("Bot läuft und ist bereit für Befehle")

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