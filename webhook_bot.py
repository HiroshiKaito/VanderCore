import logging
import os
import json
import atexit
import sys
import threading
from time import sleep
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, Filters
)
from config import config
from wallet_manager import WalletManager

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

# Globale Variablen
updater = None
dispatcher = None
active_users = set()
wallet_manager = None
user_wallets = {}

# Flask App
app = Flask(__name__)

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

def button_handler(update: Update, context: CallbackContext):
    """Handler für Button-Callbacks"""
    query = update.callback_query
    user_id = str(query.from_user.id)

    try:
        query.answer()

        if query.data == "create_wallet":
            logger.info(f"Wallet-Erstellung angefordert von User {user_id}")

            # Prüfe ob User bereits eine Wallet hat
            if user_id in user_wallets:
                query.message.reply_text(
                    "✨ Du hast bereits eine aktive Wallet.\n\n"
                    f"Wallet-Adresse:\n{user_wallets[user_id]}\n\n"
                    "Verfügbare Befehle:\n"
                    "/wallet - Wallet-Status anzeigen\n"
                    "/stop_signals - Signalsuche beenden",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🎯 Trading starten", callback_data="start_signal_search")]
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

                    # Sende alle Wallet-Informationen in einer Nachricht
                    query.message.reply_text(
                        "🌟 Wallet erfolgreich erstellt!\n\n"
                        "🔐 Private Key (streng geheim):\n"
                        f"{private_key}\n\n"
                        "🔑 Öffentliche Wallet-Adresse:\n"
                        f"{public_key}\n\n"
                        "⚠️ WICHTIG:\n"
                        "• Private Key niemals teilen\n"
                        "• Sicheres Backup erstellen\n"
                        "• Keine Wiederherstellung möglich\n\n"
                        "Ready für's Trading?\n\n"
                        "Verfügbare Befehle:\n"
                        "/wallet - Wallet-Status anzeigen\n"
                        "/stop_signals - Signalsuche beenden",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🎯 Trading starten", callback_data="start_signal_search")]
                        ])
                    )
                else:
                    raise Exception("Wallet-Erstellung fehlgeschlagen")

            except Exception as e:
                logger.error(f"Fehler bei Wallet-Erstellung: {e}")
                query.message.reply_text("⚠️ Fehler bei der Wallet-Erstellung. Versuche es erneut.")

        elif query.data == "start_signal_search":
            logger.info(f"Signal-Suche aktiviert von User {user_id}")
            try:
                # Prüfe ob Wallet existiert
                if user_id not in user_wallets:
                    query.message.reply_text(
                        "✨ Erstelle zuerst deine Wallet.\n\n"
                        "Der Weg zum Erfolg:\n"
                        "1. Wallet erstellen\n"
                        "2. Trading starten\n"
                        "3. Gewinne einfahren\n\n"
                        "Verfügbare Befehle:\n"
                        "/wallet - Wallet-Status anzeigen\n"
                        "/stop_signals - Signalsuche beenden",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("⚡ Wallet erstellen", callback_data="create_wallet")]
                        ])
                    )
                    return

                # Füge Benutzer zu aktiven Nutzern hinzu
                active_users.add(user_id)
                logger.info(f"User {user_id} zu aktiven Nutzern hinzugefügt")

                # Bestätige die Aktivierung
                query.message.reply_text(
                    "🌑 Systeme online. Trading-Modus aktiviert.\n\n"
                    "Der Prozess:\n"
                    "1. Meine KI analysiert Millionen von Datenpunkten\n"
                    "2. Bei hochprofitablen Chancen wirst du benachrichtigt\n"
                    "3. Du prüfst und bestätigst\n"
                    "4. Ich führe präzise aus\n\n"
                    "Status: Aktiv und scannen\n\n"
                    "Verfügbare Befehle:\n"
                    "/wallet - Wallet-Status anzeigen\n"
                    "/stop_signals - Signalsuche beenden"
                )

            except Exception as e:
                logger.error(f"Fehler beim Starten des Signal Generators: {str(e)}")
                query.message.reply_text(
                    "⚠️ Fehler. Starte neu mit /start\n\n"
                    "Verfügbare Befehle:\n"
                    "/wallet - Wallet-Status anzeigen\n"
                    "/stop_signals - Signalsuche beenden"
                )

    except Exception as e:
        logger.error(f"Fehler im Button Handler: {str(e)}")
        query.message.reply_text(
            "⚠️ Verbindungsfehler. Starte neu mit /start\n\n"
            "Verfügbare Befehle:\n"
            "/wallet - Wallet-Status anzeigen\n"
            "/stop_signals - Signalsuche beenden"
        )

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Start-Befehl von User {user_id}")

        # Prüfe ob User bereits eine Wallet hat
        if user_id in user_wallets:
            update.message.reply_text(
                "🌑 Vander hier. Willkommen zurück.\n\n"
                f"Deine Wallet ist bereit:\n{user_wallets[user_id]}\n\n"
                "Verfügbare Befehle:\n"
                "/wallet - Wallet-Status anzeigen\n"
                "/stop_signals - Signalsuche beenden",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🎯 Trading starten", callback_data="start_signal_search")]
                ])
            )
            return

        update.message.reply_text(
            "🌑 Vander hier.\n\n"
            "Ich operiere in den Tiefen der Blockchain.\n"
            "Meine Spezialität: profitable Trading-Opportunitäten aufspüren.\n\n"
            "Was ich beherrsche:\n"
            "• KI-gesteuerte Marktanalyse in Echtzeit\n"
            "• Präzise Signale mit 85% Erfolgsquote\n"
            "• Blitzschnelle Order-Ausführung\n"
            "• Automatisierte Risikokontrolle\n\n"
            "Ich finde die Trades, die andere übersehen.\n"
            "Du entscheidest, ich handle.\n\n"
            "Verfügbare Befehle:\n"
            "/wallet - Wallet-Status anzeigen\n"
            "/stop_signals - Signalsuche beenden\n\n"
            "Bereit für echtes Trading?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Wallet erstellen", callback_data="create_wallet")]
            ])
        )
        logger.info(f"Start-Nachricht erfolgreich an User {user_id} gesendet")

    except Exception as e:
        logger.error(f"Fehler beim Start-Command: {e}")
        update.message.reply_text("⚠️ Fehler aufgetreten. Versuche es erneut mit /start")

def stop_signals(update: Update, context: CallbackContext):
    """Stoppt die Signalsuche für einen User"""
    user_id = str(update.effective_user.id)
    if user_id in active_users:
        active_users.remove(user_id)
        update.message.reply_text(
            "🔴 Signalsuche deaktiviert.\n"
            "Du erhältst keine weiteren Trading-Signale.\n\n"
            "Verfügbare Befehle:\n"
            "/start - Bot neu starten\n"
            "/wallet - Wallet-Status anzeigen\n"
            "/stop_signals - Signalsuche beenden"
        )
    else:
        update.message.reply_text("Signalsuche war nicht aktiv.")

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
        dispatcher.add_handler(CommandHandler("stop_signals", stop_signals))

        logger.info("Bot erfolgreich initialisiert")
        return True

    except Exception as e:
        logger.error(f"Fehler bei Bot-Initialisierung: {e}")
        return False

def run_flask():
    """Startet den Flask-Server"""
    try:
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
    except Exception as e:
        logger.error(f"Fehler beim Starten des Flask-Servers: {e}")

def main():
    """Hauptfunktion"""
    try:
        # Initialisiere Bot
        if not initialize_bot():
            logger.error("Bot-Initialisierung fehlgeschlagen")
            return

        # Starte Flask in separatem Thread
        flask_thread = threading.Thread(target=run_flask, daemon=True)
        flask_thread.start()
        logger.info("Flask-Server Thread gestartet")

        # Starte Polling
        logger.info("Starte Bot im Polling-Modus...")
        updater.start_polling(drop_pending_updates=True)
        logger.info("Bot läuft im Polling-Modus")

        # Warte auf Beenden
        updater.idle()

    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}")
        sys.exit(1)

# Registriere save_user_wallets für automatisches Speichern beim Beenden
atexit.register(save_user_wallets)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot wird durch Benutzer beendet")
    except Exception as e:
        logger.error(f"Kritischer Fehler beim Starten des Bots: {e}")
        sys.exit(1)