"""
Telegram Bot mit Webhook-Integration für Solana Trading
"""
import logging
import os
import json
import atexit
from flask import Flask, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, Filters, Dispatcher
)
from config import config
from wallet_manager import WalletManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.DEBUG,  # Erhöhtes Log-Level
    handlers=[
        logging.FileHandler("webhook_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask App für Webhook
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['PROPAGATE_EXCEPTIONS'] = True

# Globale Variablen
bot = None
dispatcher = None
wallet_manager = None
user_wallets = {}
user_private_keys = {}

def setup_bot():
    """Initialisiert den Bot und registriert Handler"""
    global bot, dispatcher, wallet_manager
    try:
        logger.info("Starte Bot-Initialisierung...")

        # Überprüfe TELEGRAM_TOKEN
        if not config.TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN nicht gefunden in Umgebungsvariablen")
            logger.debug(f"Verfügbare Umgebungsvariablen: {', '.join(list(os.environ.keys()))}")
            return False

        # Initialisiere Bot
        logger.debug("Initialisiere Bot mit Token...")
        bot = Bot(token=config.TELEGRAM_TOKEN)

        # Test Bot Connection
        logger.debug("Teste Bot-Verbindung...")
        me = bot.get_me()
        logger.info(f"Bot-Verbindung erfolgreich: {me.username}")

        # Initialisiere Dispatcher
        logger.debug("Initialisiere Dispatcher...")
        dispatcher = Dispatcher(bot, None, workers=4, use_context=True)

        # Initialisiere Wallet Manager
        logger.debug("Initialisiere Wallet Manager...")
        wallet_manager = WalletManager(config.SOLANA_RPC_URL)

        # Register handlers
        logger.debug("Registriere Handler...")
        register_handlers()

        # Load wallets
        logger.debug("Lade Wallet-Daten...")
        load_user_wallets()

        logger.info("Bot-Initialisierung erfolgreich abgeschlossen")
        return True

    except Exception as e:
        logger.error(f"Kritischer Fehler bei Bot-Initialisierung: {e}", exc_info=True)
        return False

def register_handlers():
    """Registriert die Bot-Handler"""
    try:
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("wallet", wallet_command))
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
        dispatcher.add_error_handler(error_handler)
        logger.info("Handler erfolgreich registriert")
    except Exception as e:
        logger.error(f"Fehler beim Registrieren der Handler: {e}", exc_info=True)
        raise

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = update.effective_user.id
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
        logger.error(f"Fehler beim Start-Command: {e}", exc_info=True)
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

        if wallet_manager and user_id in user_private_keys:
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
        logger.error(f"Fehler beim Wallet-Command: {e}", exc_info=True)
        update.message.reply_text(
            "❌ Ein Fehler ist aufgetreten.\n"
            "Versuche es später erneut!"
        )

def button_handler(update: Update, context: CallbackContext):
    """Handler für Button-Callbacks"""
    query = update.callback_query
    user_id = str(query.from_user.id)

    try:
        query.answer()  # Bestätige den Button-Click

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
                    "Ready to trade? 🎬",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Let's go! 🚀", callback_data="start_signal_search")]
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

        elif query.data == "start_signal_search":
            logger.info(f"Signal-Suche aktiviert von User {user_id}")
            query.message.reply_text(
                "✨ Perfect! Die Signal-Suche wird bald verfügbar sein.\n\n"
                "Status: 🟡 In Vorbereitung"
            )

    except Exception as e:
        logger.error(f"Fehler im Button Handler: {e}", exc_info=True)
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
        logger.error(f"Fehler im Message Handler: {e}", exc_info=True)

def error_handler(update: Update, context: CallbackContext):
    """Fehlerbehandlung für den Bot"""
    try:
        if context.error:
            logger.error(f"Update {update} verursachte Fehler {context.error}", exc_info=True)
    except Exception as e:
        logger.error(f"Fehler im Error Handler: {e}", exc_info=True)

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
        logger.error(f"Fehler beim Speichern der Wallet-Daten: {e}", exc_info=True)

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
        logger.error(f"Fehler beim Laden der Wallet-Daten: {e}", exc_info=True)
        user_wallets = {}
        user_private_keys = {}

def cleanup():
    """Cleanup beim Beenden"""
    try:
        save_user_wallets()
        if bot:
            bot.delete_webhook()
        logger.info("Cleanup durchgeführt")
    except Exception as e:
        logger.error(f"Fehler beim Cleanup: {e}", exc_info=True)

atexit.register(cleanup)

@app.route('/' + config.TELEGRAM_TOKEN, methods=['POST'])
def webhook():
    """Verarbeitet eingehende Webhook-Anfragen"""
    try:
        json_data = request.get_json()
        update = Update.de_json(json_data, bot)
        dispatcher.process_update(update)
        return 'ok'
    except Exception as e:
        logger.error(f"Fehler bei Webhook-Verarbeitung: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@app.route('/')
def root():
    """Root route to confirm server is running"""
    try:
        me = bot.get_me() if bot else None
        return jsonify({
            'status': 'running',
            'message': 'Solana Trading Bot Server is running',
            'bot_info': me.username if me else None
        })
    except Exception as e:
        logger.error(f"Fehler in root route: {e}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)