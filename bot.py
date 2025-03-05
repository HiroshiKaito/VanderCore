import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    CallbackContext
)

from config import Config
from wallet_manager import WalletManager
from utils import format_amount, validate_amount, format_wallet_info

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class SolanaWalletBot:
    def __init__(self):
        self.config = Config()
        self.wallet_manager = WalletManager(self.config.SOLANA_RPC_URL)
        self.updater = None
        logger.info("Bot initialisiert")

    def start(self, update: Update, context: CallbackContext):
        """Start-Befehl Handler"""
        user_id = update.effective_user.id
        logger.info(f"Start-Befehl von User {user_id}")
        update.message.reply_text(
            "🚀 Willkommen beim Solana Wallet Bot!\n\n"
            "Mit diesem Bot können Sie:\n"
            "✅ Eine Solana-Wallet erstellen\n"
            "💰 Ihr Guthaben überprüfen\n"
            "💸 SOL senden und empfangen\n"
            "📱 QR-Codes für einfache Transaktionen nutzen\n\n"
            "Verfügbare Befehle:\n"
            "/start - Bot starten\n"
            "/hilfe - Zeigt diese Hilfe an\n"
            "/wallet - Wallet-Verwaltung\n"
            "/senden - SOL senden (mit QR-Scanner oder manueller Eingabe)\n"
            "/empfangen - Einzahlungsadresse als QR-Code anzeigen",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Wallet erstellen", callback_data="create_wallet")]
            ])
        )

    def help_command(self, update: Update, context: CallbackContext):
        """Hilfe-Befehl Handler"""
        user_id = update.effective_user.id
        logger.info(f"Hilfe-Befehl von User {user_id}")
        update.message.reply_text(
            "📚 Verfügbare Befehle:\n\n"
            "🔹 Basis Befehle:\n"
            "/start - Bot starten\n"
            "/hilfe - Diese Hilfe anzeigen\n\n"
            "🔹 Wallet Befehle:\n"
            "/wallet - Wallet-Info anzeigen\n"
            "/senden - SOL senden (mit QR-Scanner oder manueller Eingabe)\n"
            "/empfangen - Einzahlungsadresse als QR-Code anzeigen\n\n"
            "❓ Brauchen Sie Hilfe? Nutzen Sie /start um neu zu beginnen!"
        )

    def wallet_command(self, update: Update, context: CallbackContext):
        """Wallet-Befehl Handler"""
        user_id = update.effective_user.id
        logger.info(f"Wallet-Befehl von User {user_id}")
        address = self.wallet_manager.get_address()
        if not address:
            logger.info(f"Keine Wallet für User {user_id}")
            update.message.reply_text(
                "❌ Keine Wallet verbunden. Bitte zuerst eine Wallet erstellen.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Wallet erstellen", callback_data="create_wallet")
                ]])
            )
            return

        balance = self.wallet_manager.get_balance()
        logger.info(f"Wallet-Info abgerufen für User {user_id}, Balance: {balance}")
        update.message.reply_text(
            format_wallet_info(balance, address),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💸 Senden", callback_data="send_sol")],
                [InlineKeyboardButton("📱 QR-Code anzeigen", callback_data="show_qr")]
            ])
        )

    def send_command(self, update: Update, context: CallbackContext):
        """Senden-Befehl Handler"""
        if not self.wallet_manager.get_address():
            update.message.reply_text(
                "❌ Bitte zuerst eine Wallet erstellen!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Wallet erstellen", callback_data="create_wallet")
                ]])
            )
            return

        update.message.reply_text(
            "💸 SOL senden\n\n"
            "Wie möchten Sie die Empfängeradresse eingeben?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📱 QR-Code scannen", callback_data="scan_qr")],
                [InlineKeyboardButton("✍️ Adresse manuell eingeben", callback_data="manual_address")]
            ])
        )

    def receive_command(self, update: Update, context: CallbackContext):
        """Empfangen-Befehl Handler"""
        address = self.wallet_manager.get_address()
        if not address:
            update.message.reply_text(
                "❌ Bitte zuerst eine Wallet erstellen!",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Wallet erstellen", callback_data="create_wallet")
                ]])
            )
            return

        try:
            # Generiere QR-Code
            qr_bio = self.wallet_manager.generate_qr_code()
            update.message.reply_photo(
                photo=qr_bio,
                caption=f"📱 Ihre Wallet-Adresse als QR-Code:\n\n"
                f"`{address}`\n\n"
                f"Scannen Sie den QR-Code, um SOL zu empfangen.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Fehler bei QR-Code-Generierung: {e}")
            update.message.reply_text(
                f"📥 Ihre Wallet-Adresse zum Empfangen von SOL:\n\n"
                f"`{address}`",
                parse_mode='Markdown'
            )

    def button_handler(self, update: Update, context: CallbackContext):
        """Callback Query Handler für Buttons"""
        query = update.callback_query
        user_id = query.from_user.id
        logger.info(f"Button-Callback von User {user_id}: {query.data}")
        query.answer()

        if query.data == "create_wallet":
            logger.info(f"Erstelle neue Solana-Wallet für User {user_id}")
            public_key, private_key = self.wallet_manager.create_wallet()
            if public_key and private_key:
                logger.info(f"Solana-Wallet erfolgreich erstellt für User {user_id}")
                query.message.reply_text(
                    f"✅ Neue Solana-Wallet erstellt!\n\n"
                    f"Adresse: `{public_key}`\n\n"
                    f"🔐 Private Key:\n"
                    f"`{private_key}`\n\n"
                    f"⚠️ WICHTIG: Bewahren Sie den Private Key sicher auf! "
                    f"Er wird benötigt, um auf Ihre Wallet zuzugreifen.\n\n"
                    f"Nutzen Sie /wallet um Ihre Wallet-Informationen anzuzeigen.",
                    parse_mode='Markdown'
                )
            else:
                logger.error(f"Fehler bei Wallet-Erstellung für User {user_id}")
                query.message.reply_text("❌ Fehler beim Erstellen der Wallet!")

        elif query.data == "show_qr":
            try:
                qr_bio = self.wallet_manager.generate_qr_code()
                query.message.reply_photo(
                    photo=qr_bio,
                    caption="📱 Scannen Sie diesen QR-Code, um SOL zu senden."
                )
            except Exception as e:
                logger.error(f"Fehler bei QR-Code-Anzeige: {e}")
                query.message.reply_text("❌ Fehler beim Generieren des QR-Codes.")

        elif query.data == "scan_qr":
            try:
                query.message.reply_text("📱 Bitte halten Sie einen QR-Code vor die Kamera...")
                address = self.wallet_manager.scan_qr_code()
                if address:
                    query.message.reply_text(
                        f"✅ QR-Code gescannt!\n\n"
                        f"Empfänger-Adresse: `{address}`\n\n"
                        f"Bitte geben Sie den Betrag ein, den Sie senden möchten (in SOL):",
                        parse_mode='Markdown'
                    )
                else:
                    query.message.reply_text(
                        "❌ Kein QR-Code erkannt. Bitte versuchen Sie es erneut oder "
                        "wählen Sie 'Adresse manuell eingeben'."
                    )
            except Exception as e:
                logger.error(f"Fehler beim QR-Scan: {e}")
                query.message.reply_text(
                    "❌ Fehler beim Öffnen der Kamera. Bitte wählen Sie 'Adresse manuell eingeben'."
                )

        elif query.data == "manual_address":
            query.message.reply_text(
                "✍️ Bitte geben Sie die Empfängeradresse und den Betrag im Format ein:\n"
                "ADRESSE BETRAG\n\n"
                "Beispiel:\n"
                "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU 0.1"
            )


    def run(self):
        """Startet den Bot"""
        logger.info("Starting bot...")
        try:
            # Initialize updater with bot's token
            self.updater = Updater(token=self.config.TELEGRAM_TOKEN, use_context=True)

            # Get the dispatcher to register handlers
            dp = self.updater.dispatcher

            # Command handlers
            dp.add_handler(CommandHandler("start", self.start))
            dp.add_handler(CommandHandler("hilfe", self.help_command))
            dp.add_handler(CommandHandler("wallet", self.wallet_command))
            dp.add_handler(CommandHandler("senden", self.send_command))
            dp.add_handler(CommandHandler("empfangen", self.receive_command))

            # Callback query handler
            dp.add_handler(CallbackQueryHandler(self.button_handler))

            # Start the Bot
            logger.info("Bot is ready to handle messages")
            self.updater.start_polling()

            # Run the bot until you press Ctrl-C
            self.updater.idle()

        except Exception as e:
            logger.error(f"Error starting bot: {e}")
            raise

if __name__ == "__main__":
    bot = SolanaWalletBot()
    bot.run()