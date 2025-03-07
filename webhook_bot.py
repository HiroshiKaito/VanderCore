"""Webhook-basierter Telegram Bot mit Flask und Cloudflare Tunnel"""
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext, Dispatcher
from config import config
import os
import subprocess
import json
import signal
import atexit

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
cloudflared_process = None

def setup_cloudflare_tunnel():
    """Cloudflare Tunnel Setup"""
    try:
        # Starte cloudflared tunnel
        cmd = ['cloudflared', 'tunnel', '--url', 'http://localhost:5000']
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            universal_newlines=True
        )

        # Registriere Cleanup-Handler
        atexit.register(lambda: process.terminate() if process else None)

        # Warte und hole die Tunnel-URL
        for line in process.stdout:
            if 'trycloudflare.com' in line:
                tunnel_url = line.split('|')[0].strip()
                logger.info(f"Cloudflare Tunnel URL: {tunnel_url}")
                return tunnel_url, process

        raise Exception("Konnte keine Tunnel-URL finden")

    except Exception as e:
        logger.error(f"Fehler beim Cloudflare Tunnel Setup: {e}")
        return None, None

def setup_webhook():
    """Webhook-Setup mit Cloudflare Tunnel"""
    try:
        # Erstelle Cloudflare Tunnel
        tunnel_url, process = setup_cloudflare_tunnel()
        if not tunnel_url:
            logger.error("Kein Tunnel erstellt")
            return False

        global cloudflared_process
        cloudflared_process = process

        # Webhook URL
        webhook_url = f"{tunnel_url}/telegram-webhook"

        # Setze Webhook
        updater.bot.set_webhook(webhook_url)
        logger.info(f"Webhook erfolgreich gesetzt auf: {webhook_url}")

        return True
    except Exception as e:
        logger.error(f"Fehler beim Webhook-Setup: {e}")
        return False

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    update.message.reply_text(
        "👋 Willkommen beim Webhook-basierten Trading Bot!\n"
        "Ich bin jetzt noch stabiler und zuverlässiger."
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

def cleanup():
    """Cleanup-Funktion"""
    if cloudflared_process:
        cloudflared_process.terminate()
        logger.info("Cloudflare Tunnel beendet")

def main():
    """Hauptfunktion"""
    try:
        # Initialisiere Bot
        if not initialize_bot():
            return

        # Setup Webhook
        if not setup_webhook():
            return

        # Registriere Cleanup
        atexit.register(cleanup)

        logger.info("Starte Flask Server...")
        app.run(
            host='0.0.0.0',
            port=5000
        )

    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}")
        raise

if __name__ == '__main__':
    main()