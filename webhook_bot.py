"""Telegram Bot mit Polling-Modus und Health-Check-Server für Replit"""
import logging
from flask import Flask, request, jsonify
from telegram import Update
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, 
    CallbackContext, Dispatcher, CallbackQueryHandler
)
from config import config
import os
import json
import atexit
import sys
import requests
import threading
from time import sleep
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

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
active_users = set()  # Set für aktive Nutzer

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

def button_handler(update: Update, context: CallbackContext):
    """Handler für Button-Callbacks"""
    query = update.callback_query
    user_id = query.from_user.id

    try:
        query.answer()  # Bestätige den Button-Click

        if query.data == "start_signal_search":
            logger.info(f"Signal-Suche aktiviert von User {user_id}")
            try:
                # Füge Benutzer zu aktiven Nutzern hinzu
                active_users.add(user_id)
                logger.info(f"User {user_id} zu aktiven Nutzern hinzugefügt")

                # Bestätige die Aktivierung
                query.message.reply_text(
                    "✨ Perfect! Ich suche jetzt aktiv nach den besten Trading-Gelegenheiten für dich.\n\n"
                    "Du erhältst automatisch eine Nachricht, sobald ich ein hochwertiges Signal gefunden habe.\n\n"
                    "Status: 🟢 Signal Generator aktiv"
                )

            except Exception as e:
                logger.error(f"Detaillierter Fehler beim Starten des Signal Generators: {str(e)}")
                query.message.reply_text(
                    "❌ Fehler beim Aktivieren der Signal-Suche.\n"
                    "Bitte versuchen Sie es später erneut."
                )

    except Exception as e:
        logger.error(f"Fehler im Button Handler: {str(e)}")
        query.message.reply_text(
            "❌ Es ist ein Fehler aufgetreten.\n"
            f"Details: {str(e)}\n"
            "Bitte versuchen Sie es erneut."
        )

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = update.effective_user.id
        logger.info(f"Start-Befehl von User {user_id}")

        update.message.reply_text(
            "👋 Hey! Ich bin Dexter - der beste Solana Trading Bot auf dem Markt!\n\n"
            "Ich werde dir beim Trading helfen und:\n"
            "✅ Trading Signale mit KI-Analyse generieren\n"
            "✅ Risk Management überwachen\n"
            "✅ Dein Portfolio tracken\n"
            "✅ Marktanalysen durchführen\n\n"
            "Verfügbare Befehle:\n"
            "/wallet - Wallet-Verwaltung\n"
            "/trades - Aktive Trades anzeigen\n"
            "/hilfe - Weitere Hilfe anzeigen\n\n"
            "Ready to trade? 🚀",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Let's go! 🚀", callback_data="start_signal_search")]
            ])
        )
        logger.info(f"Start-Nachricht erfolgreich an User {user_id} gesendet")

    except Exception as e:
        logger.error(f"Fehler beim Start-Command: {e}")
        update.message.reply_text("❌ Es ist ein Fehler aufgetreten. Bitte versuche es später erneut.")

@app.route('/health')
def health_check():
    """Health Check Endpoint"""
    try:
        # Prüfe ob der Bot noch aktiv ist
        if not updater or not updater.bot:
            return jsonify({'status': 'error', 'message': 'Bot nicht initialisiert'}), 500

        return jsonify({
            'status': 'healthy',
            'bot_info': {
                'username': updater.bot.username
            },
            'uptime': 'active'
        })
    except Exception as e:
        logger.error(f"Health Check fehlgeschlagen: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def initialize_bot():
    """Initialisiere den Bot"""
    global updater, dispatcher

    try:
        # Erstelle Updater
        updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
        dispatcher = updater.dispatcher

        # Registriere Handler
        dispatcher.add_handler(CommandHandler("start", start))

        # Button Handler
        dispatcher.add_handler(CallbackQueryHandler(button_handler))

        logger.info("Bot erfolgreich initialisiert")
        return True

    except Exception as e:
        logger.error(f"Fehler bei Bot-Initialisierung: {e}")
        return False

def run_health_server():
    """Startet den Health-Check-Server"""
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False
        )
    except Exception as e:
        logger.error(f"Fehler beim Starten des Health-Check-Servers: {e}")
        raise

def main():
    """Hauptfunktion"""
    try:
        # Initialisiere Bot
        if not initialize_bot():
            return

        # Starte Keep-Alive Thread
        keep_alive_thread = threading.Thread(target=keep_alive, daemon=True)
        keep_alive_thread.start()
        logger.info("Keep-Alive Thread gestartet")

        # Starte Health-Check-Server in separatem Thread
        health_thread = threading.Thread(target=run_health_server, daemon=True)
        health_thread.start()
        logger.info("Health-Check-Server Thread gestartet")

        # Starte Polling im Hauptthread
        logger.info("Starte Bot im Polling-Modus...")
        updater.start_polling()
        logger.info("Bot läuft im Polling-Modus")

        # Blockiere bis Programm beendet wird
        updater.idle()

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