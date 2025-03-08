import logging
import os
import json
import atexit
import time
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, Filters
)
from telegram.error import TelegramError, NetworkError, TimedOut
from config import config
from wallet_manager import WalletManager

# Logger-Konfiguration
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask App für Health Check
app = Flask(__name__)

# Globale Variablen
updater = None
dispatcher = None
wallet_manager = None
user_wallets = {}
user_private_keys = {}

def initialize_bot():
    """Initialisiert den Bot"""
    global updater, dispatcher, wallet_manager

    try:
        logger.info("Starte Bot-Initialisierung...")

        # Prüfe Token
        if not config.TELEGRAM_TOKEN:
            logger.error("Kein Telegram Token gefunden!")
            return False

        # Erstelle Updater
        updater = Updater(
            token=config.TELEGRAM_TOKEN,
            use_context=True,
            request_kwargs={'read_timeout': 60, 'connect_timeout': 60}
        )
        dispatcher = updater.dispatcher

        # Teste Bot-Verbindung
        bot_info = updater.bot.get_me()
        logger.info(f"Bot verbunden als: {bot_info.username}")

        # Initialisiere Wallet Manager
        wallet_manager = WalletManager(config.SOLANA_RPC_URL)
        logger.info("Wallet Manager initialisiert")

        # Lade bestehende Wallets
        load_user_wallets()
        logger.info("Wallet-Daten geladen")

        # Registriere Handler
        register_handlers()
        logger.info("Handler registriert")

        return True

    except Exception as e:
        logger.error(f"Fehler bei Bot-Initialisierung: {e}")
        return False

def register_handlers():
    """Registriert die Bot-Handler"""
    try:
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("wallet", wallet_command))
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
        dispatcher.add_error_handler(error_handler)
        logger.info("Handler registriert")
    except Exception as e:
        logger.error(f"Fehler beim Registrieren der Handler: {e}")
        raise

@app.route('/')
def index():
    """Health Check Endpoint"""
    try:
        if updater and updater.bot:
            return jsonify({
                'status': 'healthy',
                'bot_username': updater.bot.username
            })
        return jsonify({'status': 'error', 'message': 'Bot nicht initialisiert'}), 500
    except Exception as e:
        logger.error(f"Fehler beim Health Check: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def save_user_wallets():
    """Speichert die User-Wallet-Daten"""
    try:
        data = {
            'wallets': user_wallets,
            'private_keys': user_private_keys
        }
        with open('user_wallets.json', 'w') as f:
            json.dump(data, f)
        logger.info("Wallet-Daten gespeichert")
    except Exception as e:
        logger.error(f"Fehler beim Speichern der Wallet-Daten: {e}")

def load_user_wallets():
    """Lädt die User-Wallet-Daten"""
    global user_wallets, user_private_keys
    try:
        if os.path.exists('user_wallets.json'):
            with open('user_wallets.json', 'r') as f:
                data = json.load(f)
                user_wallets = data.get('wallets', {})
                user_private_keys = data.get('private_keys', {})
            logger.info("Wallet-Daten geladen")
    except Exception as e:
        logger.error(f"Fehler beim Laden der Wallet-Daten: {e}")

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Start-Befehl von User {user_id}")

        update.message.reply_text(
            "🌑 Vander hier.\n\n"
            "Ich operiere in den Tiefen der Blockchain.\n"
            "Meine Spezialität: profitable Trading-Opportunitäten aufspüren.\n\n"
            "Was ich beherrsche:\n"
            "• KI-gesteuerte Marktanalyse in Echtzeit\n"
            "• Präzise Signale mit 85% Erfolgsquote\n"
            "• Blitzschnelle Order-Ausführung\n"
            "• Automatisierte Risikokontrolle\n\n"
            "Bereit durchzustarten?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚡ Wallet erstellen", callback_data="create_wallet")]
            ])
        )

    except Exception as e:
        logger.error(f"Fehler beim Start-Command: {e}")
        update.message.reply_text(
            "❌ Ein Fehler ist aufgetreten.\n"
            "Versuche es später erneut!"
        )

def wallet_command(update: Update, context: CallbackContext):
    """Handler für den /wallet Befehl"""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Wallet-Command von User {user_id}")

        if user_id not in user_wallets:
            update.message.reply_text(
                "⚠️ Du hast noch keine Wallet!\n"
                "Erstelle eine mit dem /start Befehl."
            )
            return

        if user_id in user_private_keys:
            wallet_manager.load_wallet(user_private_keys[user_id])

        balance = wallet_manager.get_balance()
        address = wallet_manager.get_address()

        update.message.reply_text(
            "💎 Dein Wallet-Status\n\n"
            f"💰 Guthaben: {balance:.4f} SOL\n"
            f"📍 Adresse: `{address}`\n\n"
            "Was möchtest du tun?",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 SOL erhalten", callback_data="show_qr")]
            ])
        )

    except Exception as e:
        logger.error(f"Fehler beim Wallet-Command: {e}")
        update.message.reply_text(
            "❌ Ein Fehler ist aufgetreten.\n"
            "Versuche es später erneut!"
        )

def button_handler(update: Update, context: CallbackContext):
    """Handler für Button-Callbacks"""
    query = update.callback_query
    user_id = str(query.from_user.id)

    try:
        query.answer()

        if query.data == "create_wallet":
            # Erstelle neue Wallet
            public_key, private_key = wallet_manager.create_wallet()

            if public_key and private_key:
                # Speichere Wallet-Informationen
                user_wallets[user_id] = public_key
                user_private_keys[user_id] = private_key
                save_user_wallets()

                query.message.reply_text(
                    "🌟 Wallet erfolgreich erstellt!\n\n"
                    "🔐 Private Key (streng geheim):\n"
                    f"{private_key}\n\n"
                    "🔑 Öffentliche Wallet-Adresse:\n"
                    f"{public_key}\n\n"
                    "⚠️ WICHTIG: Sichere deinen Private Key!\n\n"
                    "Was möchtest du als Nächstes tun?",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("💰 Wallet anzeigen", callback_data="show_wallet")]
                    ])
                )
            else:
                query.message.reply_text("❌ Fehler bei der Wallet-Erstellung")

        elif query.data == "show_qr":
            if user_id in user_private_keys:
                wallet_manager.load_wallet(user_private_keys[user_id])

            qr_buffer = wallet_manager.generate_qr_code()
            query.message.reply_photo(
                photo=qr_buffer,
                caption=(
                    "🎯 Hier ist dein QR-Code zum Einzahlen!\n\n"
                    "Ich sage dir Bescheid, sobald dein\n"
                    "Guthaben eingegangen ist! 🚀"
                )
            )

    except Exception as e:
        logger.error(f"Fehler im Button Handler: {e}")
        query.message.reply_text(
            "❌ Ein Fehler ist aufgetreten.\n"
            "Versuche es später erneut!"
        )

def message_handler(update: Update, context: CallbackContext):
    """Handler für normale Nachrichten"""
    try:
        update.message.reply_text(
            "Nutze die Buttons oder diese Befehle:\n"
            "/start - Bot neu starten\n"
            "/wallet - Wallet anzeigen"
        )
    except Exception as e:
        logger.error(f"Fehler im Message Handler: {e}")

def error_handler(update: Update, context: CallbackContext):
    """Fehlerbehandlung für den Bot"""
    try:
        if context.error:
            logger.error(f"Update {update} verursachte Fehler {context.error}")
    except Exception as e:
        logger.error(f"Fehler im Error Handler: {e}")

def cleanup():
    """Cleanup beim Beenden"""
    try:
        save_user_wallets()
        logger.info("Cleanup durchgeführt")
    except Exception as e:
        logger.error(f"Fehler beim Cleanup: {e}")

atexit.register(cleanup)

def run_bot():
    """Startet den Bot im Polling-Modus mit automatischem Neustart"""
    logger.info("Starte Bot im Polling-Modus...")
    while True:
        try:
            updater.start_polling(drop_pending_updates=True)
            logger.info("Bot-Polling gestartet")
            updater.idle()
        except NetworkError as e:
            logger.error(f"Netzwerkfehler: {e}")
            logger.info("Warte 10 Sekunden vor Neustart...")
            time.sleep(10)
        except TimedOut as e:
            logger.error(f"Timeout Error: {e}")
            logger.info("Warte 5 Sekunden vor Neustart...")
            time.sleep(5)
        except Exception as e:
            logger.error(f"Kritischer Fehler: {e}")
            logger.info("Warte 30 Sekunden vor Neustart...")
            time.sleep(30)
        finally:
            try:
                updater.stop()
            except Exception:
                pass

def main():
    """Hauptfunktion"""
    try:
        # Initialisiere Bot
        if not initialize_bot():
            logger.error("Bot-Initialisierung fehlgeschlagen")
            return

        # Starte Flask Server
        logger.info("Starte Flask Server auf Port 5000...")
        app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

        # Starte Bot mit automatischem Neustart
        run_bot()

    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}")
        raise

if __name__ == '__main__':
    main()