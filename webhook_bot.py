"""Telegram Bot mit Polling-Modus und Health-Check-Server für Replit"""
import logging
from flask import Flask, request, jsonify
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Updater, CommandHandler, MessageHandler, Filters, 
    CallbackContext, Dispatcher, CallbackQueryHandler
)
from config import config
from wallet_manager import WalletManager
import os
import json
import atexit
import sys
import requests
import threading
from time import sleep
import nltk

# Download NLTK data
try:
    nltk.download('punkt')
    nltk.download('averaged_perceptron_tagger')
    nltk.download('wordnet')
    nltk.download('vader_lexicon')
except Exception as e:
    print(f"NLTK Download Fehler: {e}")

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
wallet_manager = None

def keep_alive():
    """Hält den Replit-Server am Leben"""
    while True:
        try:
            logger.debug("Keep-alive ping wird ausgeführt...")
            requests.get("http://127.0.0.1:5000/health")
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

        if query.data == "create_wallet":
            logger.info(f"Wallet-Erstellung angefordert von User {user_id}")
            try:
                # Erstelle neue Wallet
                public_key, private_key = wallet_manager.create_wallet()

                if public_key and private_key:
                    # Sende private_key als private Nachricht
                    query.message.reply_text(
                        "🔐 Hier ist dein Private Key. Bewahre ihn sicher auf!\n\n"
                        f"`{private_key}`\n\n"
                        "⚠️ Teile diesen Key NIEMALS mit anderen!",
                        parse_mode='Markdown'
                    )

                    # Sende öffentliche Bestätigung
                    query.message.reply_text(
                        "✅ Wallet erfolgreich erstellt!\n\n"
                        f"Deine Wallet-Adresse: `{public_key}`\n\n"
                        "Möchtest du jetzt mit dem Trading beginnen?",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Let's trade! 🚀", callback_data="start_signal_search")]
                        ])
                    )
                else:
                    raise Exception("Wallet-Erstellung fehlgeschlagen")

            except Exception as e:
                logger.error(f"Fehler bei Wallet-Erstellung: {e}")
                query.message.reply_text("❌ Fehler bei der Wallet-Erstellung")

        elif query.data == "load_wallet":
            logger.info(f"Wallet-Import angefordert von User {user_id}")
            query.message.reply_text(
                "🔑 Bitte sende mir deinen Private Key, um deine Wallet zu laden.\n\n"
                "⚠️ Sende den Key nur in einem privaten Chat!"
            )
            # Setze den nächsten Handler für den Private Key
            context.user_data['expecting_private_key'] = True

        elif query.data == "start_signal_search":
            logger.info(f"Signal-Suche aktiviert von User {user_id}")
            try:
                # Prüfe ob Wallet existiert
                if not wallet_manager.get_address():
                    query.message.reply_text(
                        "❌ Bitte erstelle oder lade zuerst eine Wallet!",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Neue Wallet erstellen", callback_data="create_wallet")],
                            [InlineKeyboardButton("Existierende Wallet laden", callback_data="load_wallet")]
                        ])
                    )
                    return

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
                logger.error(f"Fehler beim Starten des Signal Generators: {str(e)}")
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
            "Bevor wir loslegen können, brauchst du eine Wallet. "
            "Was möchtest du tun?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Neue Wallet erstellen", callback_data="create_wallet")],
                [InlineKeyboardButton("Existierende Wallet laden", callback_data="load_wallet")]
            ])
        )
        logger.info(f"Start-Nachricht erfolgreich an User {user_id} gesendet")

    except Exception as e:
        logger.error(f"Fehler beim Start-Command: {e}")
        update.message.reply_text("❌ Es ist ein Fehler aufgetreten. Bitte versuche es später erneut.")

def handle_private_key(update: Update, context: CallbackContext):
    """Handler für eingehende Private Keys"""
    try:
        # Lösche die Nachricht sofort für Sicherheit
        update.message.delete()

        if wallet_manager.load_wallet(update.message.text):
            update.message.reply_text(
                "✅ Wallet erfolgreich geladen!\n\n"
                "Möchtest du jetzt mit dem Trading beginnen?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Let's trade! 🚀", callback_data="start_signal_search")]
                ])
            )
        else:
            update.message.reply_text("❌ Ungültiger Private Key")

    except Exception as e:
        logger.error(f"Fehler beim Laden der Wallet: {e}")
        update.message.reply_text("❌ Fehler beim Laden der Wallet")
    finally:
        # Zurücksetzen des Erwartungsstatus
        if 'expecting_private_key' in context.user_data:
            del context.user_data['expecting_private_key']

def message_handler(update: Update, context: CallbackContext):
    """Genereller Message Handler"""
    if context.user_data.get('expecting_private_key'):
        handle_private_key(update, context)
    else:
        # Handle andere Nachrichten hier
        pass

@app.route('/')
def index():
    """Root-Route für Health-Check"""
    return jsonify({'status': 'running'})

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

def initialize_bot():
    """Initialisiere den Bot"""
    global updater, dispatcher, wallet_manager

    try:
        # Erstelle Updater
        updater = Updater(token=config.TELEGRAM_TOKEN, use_context=True)
        dispatcher = updater.dispatcher

        # Initialisiere Wallet Manager
        wallet_manager = WalletManager(config.SOLANA_RPC_URL)

        # Registriere Handler
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        dispatcher.add_handler(MessageHandler(
            Filters.text & ~Filters.command,
            message_handler
        ))

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