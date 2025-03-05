import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext
)
from telegram.error import Conflict, NetworkError, TelegramError
from datetime import datetime
from config import Config
from wallet_manager import WalletManager
from utils import format_amount, validate_amount, format_wallet_info
from signal_processor import SignalProcessor
from dex_connector import DexConnector
from automated_signal_generator import AutomatedSignalGenerator


# Logging Setup mit detailliertem Format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Debug-Level für mehr Details
)
logger = logging.getLogger(__name__)

class SolanaWalletBot:
    def __init__(self):
        """Initialisiert den Bot mit Konfiguration"""
        logger.info("Initialisiere Bot...")
        self.config = Config()

        # Überprüfe Token-Format (nur die ersten 10 Zeichen für Sicherheit)
        if not self.config.TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN nicht gefunden!")
            raise ValueError("TELEGRAM_TOKEN muss gesetzt sein!")
        else:
            token_prefix = self.config.TELEGRAM_TOKEN[:10] + "..."
            logger.info(f"Bot Token gefunden (Prefix: {token_prefix})")
            logger.info(f"Admin User ID konfiguriert: {self.config.ADMIN_USER_ID}")

        self.wallet_manager = WalletManager(self.config.SOLANA_RPC_URL)
        self.updater = None
        self.waiting_for_address = {}
        self.waiting_for_trade_amount = False

        # Initialize DexConnector and SignalProcessor
        self.dex_connector = DexConnector()
        self.signal_processor = SignalProcessor()

        # Initialize AutomatedSignalGenerator
        self.signal_generator = None  # Will be initialized after updater
        logger.info("Bot erfolgreich initialisiert")

    def error_handler(self, update: object, context: CallbackContext) -> None:
        """Verbesserte Fehlerbehandlung"""
        logger.error(f"Fehler aufgetreten: {context.error}")
        try:
            raise context.error
        except Conflict:
            logger.error("Konflikt mit anderer Bot-Instanz erkannt")
            if self.updater:
                logger.info("Versuche Polling neu zu starten...")
                self.updater.stop()
                self.updater.start_polling(drop_pending_updates=True)
        except NetworkError:
            logger.error("Netzwerkfehler erkannt")
            if self.updater:
                logger.info("Versuche Verbindung wiederherzustellen...")
                self.updater.stop()
                self.updater.start_polling(drop_pending_updates=True)
        except TelegramError as e:
            logger.error(f"Telegram API Fehler: {e}")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler: {e}")

    def start(self, update: Update, context: CallbackContext) -> None:
        """Start-Befehl Handler"""
        logger.debug("Start-Befehl empfangen")
        user_id = update.effective_user.id
        logger.info(f"Start-Befehl von User {user_id}")

        try:
            logger.debug(f"Sende Start-Nachricht an User {user_id}")
            update.message.reply_text(
                "👋 Hey! Ich bin Dexter - der beste Solana Trading Bot auf dem Markt!\n\n"
                "🚀 Mit meiner hochentwickelten KI-Analyse finde ich die profitabelsten Trading-Gelegenheiten für dich. "
                "Lehne dich zurück und lass mich die Arbeit machen!\n\n"
                "Was ich für dich tun kann:\n"
                "✅ Top Trading-Signale automatisch erkennen\n"
                "💰 Deine Solana-Wallet sicher verwalten\n"
                "📊 Risiken intelligent analysieren\n"
                "🎯 Gewinnchancen maximieren\n\n"
                "Verfügbare Befehle:\n"
                "/wallet - Wallet-Verwaltung\n"
                "/signal - Trading Signale anzeigen\n"
                "/trades - Aktive Trades anzeigen\n"
                "/hilfe - Weitere Hilfe anzeigen\n\n"
                "Ready to trade? 🎬",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Wallet erstellen", callback_data="create_wallet")]
                ])
            )
            logger.debug("Start-Nachricht erfolgreich gesendet")
        except Exception as e:
            logger.error(f"Fehler beim Senden der Start-Nachricht: {e}")

    def help_command(self, update: Update, context: CallbackContext) -> None:
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
            "/senden - SOL senden\n"
            "/empfangen - Einzahlungsadresse anzeigen\n\n"
            "🔹 Trading Befehle:\n"
            "/signal - Aktuelle Trading Signale anzeigen\n"
            "/trades - Aktuelle Trades anzeigen\n"
            "❓ Brauchen Sie Hilfe? Nutzen Sie /start um neu zu beginnen!"
        )

    def wallet_command(self, update: Update, context: CallbackContext) -> None:
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

    def send_command(self, update: Update, context: CallbackContext) -> None:
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

    def receive_command(self, update: Update, context: CallbackContext) -> None:
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

    def handle_signal_command(self, update: Update, context: CallbackContext) -> None:
        """Handler für den /signal Befehl - zeigt aktuelle Trading Signale"""
        try:
            active_signals = self.signal_processor.get_active_signals()

            if not active_signals:
                update.message.reply_text(
                    "🔍 Aktuell keine aktiven Trading-Signale verfügbar.\n"
                    "Neue Signale werden automatisch analysiert und angezeigt."
                )
                return

            for idx, signal in enumerate(active_signals):
                signal_message = (
                    f"📊 Trading Signal #{idx + 1}\n\n"
                    f"Pair: {signal['pair']}\n"
                    f"Signal: {'📈 LONG' if signal['direction'] == 'long' else '📉 SHORT'}\n"
                    f"Einstieg: {signal['entry']:.2f} USDC\n"
                    f"Stop Loss: {signal['stop_loss']:.2f} USDC\n"
                    f"Take Profit: {signal['take_profit']:.2f} USDC\n\n"
                    f"📈 Erwarteter Profit: {signal['expected_profit']:.1f}%\n"
                    f"✨ Signal-Qualität: {signal['signal_quality']}/10\n\n"
                    f"Möchten Sie dieses Signal handeln?"
                )

                # Erstelle Inline-Buttons für die Interaktion
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Handeln", callback_data=f"trade_signal_{idx}"),
                        InlineKeyboardButton("❌ Ignorieren", callback_data="ignore_signal")
                    ]
                ]

                update.message.reply_text(
                    signal_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der Signale: {e}")
            update.message.reply_text("❌ Fehler beim Abrufen der Trading-Signale.")

    def handle_trades_command(self, update: Update, context: CallbackContext) -> None:
        """Handler für den /trades Befehl - zeigt aktuelle Trades"""
        try:
            executed_signals = self.signal_processor.get_executed_signals()

            if not executed_signals:
                update.message.reply_text(
                    "📊 Keine aktiven Trades\n\n"
                    "Nutzen Sie /signal um neue Trading-Signale zu sehen."
                )
                return

            for idx, trade in enumerate(executed_signals):
                trade_message = (
                    f"🔄 Aktiver Trade #{idx + 1}\n\n"
                    f"Pair: {trade['pair']}\n"
                    f"Position: {'📈 LONG' if trade['direction'] == 'long' else '📉 SHORT'}\n"
                    f"Einstieg: {trade['entry']:.2f} USDC\n"
                    f"Stop Loss: {trade['stop_loss']:.2f} USDC\n"
                    f"Take Profit: {trade['take_profit']:.2f} USDC\n"
                    f"Erwarteter Profit: {trade['expected_profit']:.1f}%\n\n"
                    f"⏰ Eröffnet: {datetime.fromtimestamp(trade['timestamp']).strftime('%d.%m.%Y %H:%M:%S')}"
                )

                keyboard = [
                    [InlineKeyboardButton("🔚 Position schließen", callback_data=f"close_trade_{idx}")]
                ]

                update.message.reply_text(
                    trade_message,
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )

        except Exception as e:
            logger.error(f"Fehler beim Anzeigen der Trades: {e}")
            update.message.reply_text("❌ Fehler beim Abrufen der aktiven Trades.")

    def handle_text(self, update: Update, context: CallbackContext) -> None:
        """Verarbeitet Textnachrichten"""
        user_id = update.effective_user.id
        logger.debug(f"Textnachricht von User {user_id} empfangen")

        try:
            text = update.message.text.strip()
            logger.debug(f"Verarbeite Eingabe: {text}")

            # Handle generic messages or unknown commands
            update.message.reply_text(
                "❓ Ich verstehe diesen Befehl nicht.\n"
                "Nutzen Sie /hilfe um alle verfügbaren Befehle zu sehen."
            )

        except Exception as e:
            logger.error(f"Fehler bei der Textverarbeitung: {e}")
            update.message.reply_text("❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.")

    def button_handler(self, update: Update, context: CallbackContext) -> None:
        """Callback Query Handler für Buttons"""
        query = update.callback_query
        user_id = query.from_user.id
        logger.info(f"Button-Callback von User {user_id}: {query.data}")

        try:
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
                        f"⚠️ WICHTIG: Bewahren Sie den Private Key sicher auf!",
                        parse_mode='Markdown'
                    )

                    # Neue motivierende Nachricht mit Button
                    query.message.reply_text(
                        "🎯 Sehr gut! Lass uns nach profitablen Trading-Signalen suchen!\n\n"
                        "Ich analysiere den Markt rund um die Uhr und melde mich sofort, "
                        "wenn ich eine vielversprechende Gelegenheit gefunden habe.",
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("🚀 Let's go!", callback_data="start_signal_search")]
                        ])
                    )
                else:
                    logger.error(f"Fehler bei Wallet-Erstellung für User {user_id}")
                    query.message.reply_text("❌ Fehler beim Erstellen der Wallet!")

            elif query.data == "start_signal_search":
                query.message.reply_text(
                    "✨ Perfect! Ich suche jetzt aktiv nach den besten Trading-Gelegenheiten für dich.\n\n"
                    "Du erhältst automatisch eine Nachricht, sobald ich ein hochwertiges Signal gefunden habe.\n"
                    "Die Signale kannst du auch jederzeit mit /signal abrufen."
                )

            elif query.data == "ignore_signal":
                query.message.reply_text(
                    "Signal wurde ignoriert. Sie erhalten weiterhin neue Signale."
                )

        except Exception as e:
            logger.error(f"Fehler im Button Handler: {e}")
            query.message.reply_text("❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.")

    def run(self):
        """Startet den Bot"""
        logger.info("Starting bot...")
        try:
            # Initialize updater with bot's token
            logger.debug(f"Versuche Bot mit Token zu initialisieren...")
            self.updater = Updater(token=self.config.TELEGRAM_TOKEN, use_context=True)
            logger.debug("Updater initialisiert")

            # Initialize DEX connection
            self.dex_connector.initialize()

            # Initialize and start signal generator
            self.signal_generator = AutomatedSignalGenerator(
                self.dex_connector,
                self.signal_processor,
                self
            )
            self.signal_generator.start()
            logger.info("Automatischer Signal-Generator gestartet")

            # Get the dispatcher to register handlers
            dp = self.updater.dispatcher
            logger.debug("Dispatcher erhalten")

            # Add error handler
            dp.add_error_handler(self.error_handler)
            logger.debug("Error Handler registriert")

            # Command handlers
            logger.debug("Registriere Command Handler...")
            dp.add_handler(CommandHandler("start", self.start))
            dp.add_handler(CommandHandler("hilfe", self.help_command))
            dp.add_handler(CommandHandler("wallet", self.wallet_command))
            dp.add_handler(CommandHandler("senden", self.send_command))
            dp.add_handler(CommandHandler("empfangen", self.receive_command))
            dp.add_handler(CommandHandler("signal", self.handle_signal_command))
            dp.add_handler(CommandHandler("trades", self.handle_trades_command))
            logger.debug("Command Handler registriert")

            # Callback query handler
            dp.add_handler(CallbackQueryHandler(self.button_handler))
            logger.debug("Callback Query Handler registriert")

            # Message handler for text
            dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_text))
            logger.debug("Text Message Handler registriert")

            # Log all registered handlers
            handlers = [handler.__class__.__name__ for handler in dp.handlers[0]]
            logger.info(f"Registrierte Handler: {handlers}")

            # Start the Bot
            logger.info("Bot startet Polling...")
            self.updater.start_polling(timeout=30, drop_pending_updates=True)
            logger.info("Bot ist bereit für Nachrichten")

            # Run the bot until you press Ctrl-C
            self.updater.idle()

        except Exception as e:
            logger.error(f"Kritischer Fehler beim Starten des Bots: {e}")
            if self.signal_generator:
                self.signal_generator.stop()
            raise

if __name__ == "__main__":
    bot = SolanaWalletBot()
    bot.run()