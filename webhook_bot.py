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
user_wallets = {}  # Dictionary zur Speicherung der Wallet-Adressen pro User

def save_user_wallets():
    """Speichert die User-Wallet-Zuordnung"""
    try:
        with open('user_wallets.json', 'w') as f:
            json.dump(user_wallets, f)
        logger.info("User-Wallet-Zuordnung gespeichert")
    except Exception as e:
        logger.error(f"Fehler beim Speichern der User-Wallet-Zuordnung: {e}")

def load_user_wallets():
    """Lädt die User-Wallet-Zuordnung"""
    global user_wallets
    try:
        if os.path.exists('user_wallets.json'):
            with open('user_wallets.json', 'r') as f:
                user_wallets = json.load(f)
            logger.info("User-Wallet-Zuordnung geladen")
    except Exception as e:
        logger.error(f"Fehler beim Laden der User-Wallet-Zuordnung: {e}")

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
    user_id = str(query.from_user.id)

    try:
        query.answer()  # Bestätige den Button-Click

        if query.data == "create_wallet":
            logger.info(f"Wallet-Erstellung angefordert von User {user_id}")

            # Prüfe ob User bereits eine Wallet hat
            if user_id in user_wallets:
                query.message.reply_text(
                    "⚔️ Deine Wallet existiert bereits in den Schatten.\n\n"
                    f"`{user_wallets[user_id]}`\n\n"
                    "Die Märkte rufen. Bist du bereit?",
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("⚡ Handel beginnen", callback_data="start_signal_search")]
                    ])
                )
                return

            try:
                # Erstelle neue Wallet
                public_key, private_key = wallet_manager.create_wallet()

                if public_key and private_key:
                    # Speichere Wallet-Adresse für User
                    user_wallets[user_id] = public_key
                    save_user_wallets()

                    # Sende private_key als private Nachricht
                    query.message.reply_text(
                        "🔮 Dein Schlüssel zur Macht. Bewahre ihn gut.\n\n"
                        f"`{private_key}`\n\n"
                        "⚠️ Merke dir:\n"
                        "• Teile ihn mit niemandem\n"
                        "• Verliere ihn nicht\n"
                        "• Es gibt keine zweite Chance",
                        parse_mode='Markdown'
                    )

                    # Sende öffentliche Bestätigung
                    query.message.reply_text(
                        "⚔️ Die Schatten haben dich erwählt.\n\n"
                        f"Deine Wallet-Adresse:\n`{public_key}`\n\n"
                        "Die Märkte warten nicht. Bist du bereit?",
                        parse_mode='Markdown',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("⚡ Handel beginnen", callback_data="start_signal_search")]
                        ])
                    )
                else:
                    raise Exception("Wallet-Erstellung fehlgeschlagen")

            except Exception as e:
                logger.error(f"Fehler bei Wallet-Erstellung: {e}")
                query.message.reply_text("⚠️ Die Schatten verweigern uns den Zugang. Versuche es erneut.")

        elif query.data == "start_signal_search":
            logger.info(f"Signal-Suche aktiviert von User {user_id}")
            try:
                # Prüfe ob Wallet existiert
                if user_id not in user_wallets:
                    query.message.reply_text(
                        "⚔️ Erst die Wallet, dann der Handel.\n\n"
                        "Der Weg ist klar:\n"
                        "1. Erschaffe deine Wallet\n"
                        "2. Tauche ein in die Märkte\n"
                        "3. Ernte die Belohnung",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔮 Wallet erschaffen", callback_data="create_wallet")]
                        ])
                    )
                    return

                # Füge Benutzer zu aktiven Nutzern hinzu
                active_users.add(user_id)
                logger.info(f"User {user_id} zu aktiven Nutzern hinzugefügt")

                # Bestätige die Aktivierung
                query.message.reply_text(
                    "⚔️ Die Jagd beginnt.\n\n"
                    "So agieren wir:\n"
                    "1. Ich durchstreife die Märkte\n"
                    "2. Finde ich Beute, kontaktiere ich dich\n"
                    "3. Du entscheidest über den Schlag\n"
                    "4. Ich führe aus. Präzise. Tödlich.\n\n"
                    "⚡ Status: Bereit zum Zuschlagen"
                )

            except Exception as e:
                logger.error(f"Fehler beim Starten des Signal Generators: {str(e)}")
                query.message.reply_text(
                    "⚠️ Die Schatten sind unruhig.\n"
                    "Starte neu mit /start"
                )

    except Exception as e:
        logger.error(f"Fehler im Button Handler: {str(e)}")
        query.message.reply_text(
            "⚠️ Die Verbindung zu den Schatten ist unterbrochen.\n"
            "Kehre zurück mit /start"
        )

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Start-Befehl von User {user_id}")

        # Prüfe ob User bereits eine Wallet hat
        if user_id in user_wallets:
            update.message.reply_text(
                "⚔️ Willkommen zurück in den Schatten der Blockchain.\n\n"
                f"Deine Wallet ist bereit:\n`{user_wallets[user_id]}`\n\n"
                "Die Märkte warten nicht. Sollen wir?",
                parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⚡ Handel beginnen", callback_data="start_signal_search")]
                ])
            )
            return

        update.message.reply_text(
            "⚔️ Ich bin Vander. Der Wächter der Solana-Schatten.\n\n"
            "Was ich dir biete:\n"
            "🔮 Präzise Marktsignale aus den Tiefen der Blockchain\n"
            "⚡ Blitzschnelle Ausführung deiner Befehle\n"
            "🛡️ Schutz deines Kapitals durch ausgeklügelte Strategien\n\n"
            "Die Zeit ist gekommen. Bist du bereit, in die Unterwelt des Tradings einzutauchen?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔮 Wallet erschaffen", callback_data="create_wallet")]
            ])
        )
        logger.info(f"Start-Nachricht erfolgreich an User {user_id} gesendet")

    except Exception as e:
        logger.error(f"Fehler beim Start-Command: {e}")
        update.message.reply_text("⚠️ Die Schatten verbergen uns. Versuche es erneut mit /start")

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

        # Lade bestehende User-Wallet-Zuordnungen
        load_user_wallets()

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

atexit.register(save_user_wallets) #Register the function to save user wallets on exit

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot wird durch Benutzer beendet")
    except Exception as e:
        logger.error(f"=== Kritischer Fehler beim Starten des Bots: {e} ===")
        sys.exit(1)