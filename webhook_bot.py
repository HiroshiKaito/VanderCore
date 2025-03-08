"""
Telegram Bot mit Webhook-Integration für Solana Trading
"""
import logging
import os
import json
import atexit
import time
import threading
import socket
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from flask import Flask, jsonify, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, Filters, Dispatcher
)
from telegram.error import TelegramError, NetworkError, TimedOut
from config import config
from wallet_manager import WalletManager

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler("webhook_bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Flask App für Webhook
app = Flask(__name__)

# Konfiguriere Flask
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
        # Initialisiere Bot
        bot = Bot(token=config.TELEGRAM_TOKEN)
        dispatcher = Dispatcher(bot, None, workers=4, use_context=True)
        wallet_manager = WalletManager(config.SOLANA_RPC_URL)

        # Register handlers
        register_handlers()

        # Load wallets
        load_user_wallets()

        logger.info(f"Bot initialized successfully: {bot.get_me().username}")
        return True
    except Exception as e:
        logger.error(f"Error initializing bot: {e}")
        return False

def get_bot_info():
    """Returns bot info for health checks"""
    try:
        return bot.get_me() if bot else None
    except Exception as e:
        logger.error(f"Error getting bot info: {e}")
        return None

def register_handlers():
    """Registriert die Bot-Handler"""
    try:
        dispatcher.add_handler(CommandHandler("start", start))
        dispatcher.add_handler(CommandHandler("wallet", wallet_command))
        dispatcher.add_handler(CallbackQueryHandler(button_handler))
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
        dispatcher.add_error_handler(error_handler)
        logger.info("Handlers registered successfully")
    except Exception as e:
        logger.error(f"Error registering handlers: {e}")
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
        logger.error(f"Fehler beim Cleanup: {e}")

atexit.register(cleanup)

class WebhookManager:
    def __init__(self):
        self.active = False
        self.last_check = 0
        self.error_count = 0
        self.max_retries = 3
        self.check_interval = 300  # 5 Minuten
        self.webhook_url = None
        self.base_url = None
        self.health_status = True

    def check_port_open(self, host, port):
        """Überprüft ob ein Port erreichbar ist"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        try:
            result = sock.connect_ex((host, port))
            return result == 0
        finally:
            sock.close()

    def check_connectivity(self):
        """Überprüft die Netzwerkverbindung"""
        try:
            if not self.check_port_open('0.0.0.0', 5000):
                logger.error("Port 5000 ist nicht erreichbar")
                return False

            if not bot:
                return False

            # Prüfe Telegram API Verbindung
            bot.get_me()
            return True
        except Exception as e:
            logger.error(f"Konnektivitätsprüfung fehlgeschlagen: {e}")
            return False

    def get_replit_domain(self):
        """Ermittelt die aktuelle Replit-Domain"""
        try:
            repl_owner = os.environ.get('REPL_OWNER')
            repl_slug = os.environ.get('REPL_SLUG')
            repl_id = os.environ.get('REPL_ID')

            # Prüfe verschiedene Domain-Varianten
            domains = [
                f"{repl_slug}.{repl_owner}.repl.co",
                f"{repl_id}.id.repl.co",
                f"{repl_slug}.repl.co"
            ]

            for domain in domains:
                if domain and self.validate_domain(domain):
                    return f"https://{domain}"

            return None
        except Exception as e:
            logger.error(f"Fehler bei Domain-Ermittlung: {e}")
            return None

    def validate_domain(self, domain):
        """Validiert eine Domain"""
        try:
            socket.gethostbyname(domain)
            return True
        except socket.gaierror:
            return False

    def setup_webhook(self):
        """Richtet den Webhook ein"""
        try:
            if not self.check_connectivity():
                logger.error("Keine Verbindung möglich")
                return False

            base_url = self.get_replit_domain()
            if not base_url:
                logger.error("Keine gültige Domain gefunden")
                return False

            webhook_url = f"{base_url}/{config.TELEGRAM_TOKEN}"
            logger.info(f"Setze Webhook-URL: {webhook_url}")

            # Lösche alten Webhook
            bot.delete_webhook()
            time.sleep(1)  # Warte kurz nach dem Löschen

            # Setze neuen Webhook mit optimierten Einstellungen
            bot.set_webhook(
                url=webhook_url,
                allowed_updates=Update.ALL_TYPES,
                drop_pending_updates=True,
                max_connections=40
            )

            # Verifiziere Setup
            webhook_info = bot.get_webhook_info()
            if webhook_info.url == webhook_url:
                self.webhook_url = webhook_url
                self.active = True
                self.error_count = 0
                self.health_status = True
                logger.info("Webhook erfolgreich eingerichtet")
                return True

            logger.error("Webhook-URL stimmt nicht überein")
            return False

        except Exception as e:
            logger.error(f"Fehler beim Webhook-Setup: {e}")
            return False

    def monitor(self):
        """Überwacht den Webhook-Status"""
        retry_delays = [5, 15, 30, 60, 300]
        current_retry = 0

        while True:
            try:
                # Prüfe Konnektivität und Webhook-Status
                if not self.active or not self.check_connectivity():
                    delay = retry_delays[min(current_retry, len(retry_delays) - 1)]
                    logger.info(f"Webhook inaktiv, versuche Neustart in {delay} Sekunden")
                    time.sleep(delay)

                    if self.setup_webhook():
                        current_retry = 0
                        continue

                    current_retry += 1
                    continue

                # Prüfe Webhook-Status
                webhook_info = bot.get_webhook_info()
                if (webhook_info.url != self.webhook_url or
                    webhook_info.last_error_date or
                    not self.check_connectivity()):
                    logger.warning("Webhook-Problem erkannt")
                    self.active = False
                    self.health_status = False
                    current_retry = 0
                    continue

                self.health_status = True
                time.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Fehler bei Webhook-Überwachung: {e}")
                self.health_status = False
                time.sleep(60)

webhook_manager = WebhookManager()

@app.route('/' + config.TELEGRAM_TOKEN, methods=['POST'])
def webhook():
    """Verarbeitet eingehende Webhook-Anfragen"""
    try:
        if not webhook_manager.active:
            return jsonify({'error': 'Webhook nicht aktiv'}), 503

        json_data = request.get_json()
        update = Update.de_json(json_data, bot)
        dispatcher.process_update(update)
        return 'ok'
    except Exception as e:
        logger.error(f"Fehler bei Webhook-Verarbeitung: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health_check():
    """Health Check Endpoint"""
    try:
        status = {
            'status': 'healthy' if webhook_manager.health_status else 'degraded',
            'bot_info': get_bot_info(),
            'webhook_url': webhook_manager.webhook_url,
            'error_count': webhook_manager.error_count,
            'last_check': webhook_manager.last_check,
            'connectivity': webhook_manager.check_connectivity()
        }

        return jsonify(status)

    except Exception as e:
        logger.error(f"Fehler beim Health Check: {e}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def main():
    """Hauptfunktion"""
    try:
        # Starte Webhook-Monitor in separatem Thread
        if not setup_bot():
            logger.error("Bot setup failed. Exiting.")
            return

        monitor_thread = threading.Thread(target=webhook_manager.monitor, daemon=True)
        monitor_thread.start()
        logger.info("Webhook-Monitor gestartet")

        # Initialer Webhook-Setup
        if not webhook_manager.setup_webhook():
            logger.error("Initialer Webhook-Setup fehlgeschlagen")
            # Wird vom Monitor automatisch wiederholt

        # Starte Flask Server
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=False,
            use_reloader=False,
            threaded=True
        )

    except Exception as e:
        logger.error(f"Fataler Fehler: {e}")
        cleanup()
        raise

if __name__ == '__main__':
    main()