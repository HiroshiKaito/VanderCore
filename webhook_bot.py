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
                        "🔐 Hier ist dein geheimer Schlüssel - dein Zugang zur Welt des Tradings!\n\n"
                        f"`{private_key}`\n\n"
                        "🚨 WICHTIG: Bewahre diesen Schlüssel absolut sicher auf!\n"
                        "🔒 Teile ihn NIE mit anderen\n"
                        "📝 Speichere ihn an einem sicheren Ort\n"
                        "⚠️ Bei Verlust gibt es KEINE Wiederherstellung",
                        parse_mode='Markdown'
                    )

                    # Sende öffentliche Bestätigung
                    query.message.reply_text(
                        "🎉 Perfekt! Deine Wallet wurde erfolgreich erstellt!\n\n"
                        f"🔑 Deine Wallet-Adresse:\n`{public_key}`\n\n"
                        "🚀 Bereit für dein Trading-Abenteuer?\n"
                        "Drücke den Button und lass uns durchstarten! 💪",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🎯 Trading starten!", callback_data="start_signal_search")]
                        ])
                    )
                else:
                    raise Exception("Wallet-Erstellung fehlgeschlagen")

            except Exception as e:
                logger.error(f"Fehler bei Wallet-Erstellung: {e}")
                query.message.reply_text("❌ Ups! Bei der Wallet-Erstellung ist etwas schiefgelaufen. Bitte versuche es erneut!")

        elif query.data == "start_signal_search":
            logger.info(f"Signal-Suche aktiviert von User {user_id}")
            try:
                # Prüfe ob Wallet existiert
                if not wallet_manager.get_address():
                    query.message.reply_text(
                        "⚠️ Moment mal! Du brauchst erst eine Wallet, bevor es losgehen kann!\n\n"
                        "Keine Sorge, das ist schnell erledigt:",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("💎 Neue Wallet erstellen", callback_data="create_wallet")]
                        ])
                    )
                    return

                # Füge Benutzer zu aktiven Nutzern hinzu
                active_users.add(user_id)
                logger.info(f"User {user_id} zu aktiven Nutzern hinzugefügt")

                # Bestätige die Aktivierung
                query.message.reply_text(
                    "🌟 Fantastisch! Dein Trading-Abenteuer beginnt!\n\n"
                    "🤖 Ich scanne jetzt aktiv den Markt nach den besten Trading-Gelegenheiten für dich.\n\n"
                    "📊 Meine KI-Analyse berücksichtigt:\n"
                    "📈 Technische Indikatoren\n"
                    "🌍 Marktstimmung\n"
                    "💡 Trendanalysen\n"
                    "🎯 Risikobewertung\n\n"
                    "🔔 Du erhältst sofort eine Benachrichtigung, wenn ich ein vielversprechendes Signal entdecke!\n\n"
                    "Status: 🟢 Aktiv und bereit"
                )

            except Exception as e:
                logger.error(f"Fehler beim Starten des Signal Generators: {str(e)}")
                query.message.reply_text(
                    "❌ Hoppla! Beim Aktivieren der Signal-Suche gab es einen kleinen Stolperstein.\n"
                    "🔄 Bitte versuche es einfach noch einmal!"
                )

    except Exception as e:
        logger.error(f"Fehler im Button Handler: {str(e)}")
        query.message.reply_text(
            "❌ Ups! Da ist etwas schiefgelaufen.\n"
            "🔄 Bitte versuche es erneut!"
        )

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = update.effective_user.id
        logger.info(f"Start-Befehl von User {user_id}")

        update.message.reply_text(
            "🤖 Yo! Dexter hier - dein autonomer Trading-Mastermind auf Solana!\n\n"
            "💪 Was mich so besonders macht?\n"
            "• Ich trade 24/7 vollautomatisch für dich\n"
            "• Meine KI trifft sekundenschnelle Entscheidungen\n"
            "• Ich führe die Trades selbstständig aus - keine manuellen Eingaben nötig\n"
            "• Maximale Performance durch Real-Time Marktanalyse\n\n"
            "🎯 Meine Mission: Dein Portfolio auf's nächste Level bringen!\n\n"
            "⚡ Ready für automated Trading?\n"
            "Erstell dir 'ne Wallet und lass uns loslegen! 🚀",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💎 Trading-Wallet erstellen", callback_data="create_wallet")]
            ])
        )
        logger.info(f"Start-Nachricht erfolgreich an User {user_id} gesendet")

    except Exception as e:
        logger.error(f"Fehler beim Start-Command: {e}")
        update.message.reply_text("❌ Ups! System-Timeout. Hit me up mit /start für'n Neustart! 🔄")

def message_handler(update: Update, context: CallbackContext):
    """Genereller Message Handler"""
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