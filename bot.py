import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Filters,
    CallbackContext,
)

from config import Config
from wallet_manager import WalletManager
from dex_connector import DexConnector
from signal_processor import SignalProcessor
from chart_analyzer import ChartAnalyzer
from utils import format_amount, validate_amount, create_trade_message, format_wallet_info

# Logging Setup
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

class TradingBot:
    def __init__(self):
        self.config = Config()
        self.wallet_manager = WalletManager(self.config.SOLANA_RPC_URL)
        self.dex_connector = DexConnector()
        self.signal_processor = SignalProcessor()
        self.chart_analyzer = ChartAnalyzer()
        self.updater = None

    def start(self, update: Update, context: CallbackContext):
        """Start-Befehl Handler"""
        update.message.reply_text(
            self.config.WELCOME_MESSAGE,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Wallet verbinden", callback_data="connect_wallet")],
                [InlineKeyboardButton("📊 Trading starten", callback_data="start_trading")]
            ])
        )

    def help_command(self, update: Update, context: CallbackContext):
        """Hilfe-Befehl Handler"""
        update.message.reply_text(self.config.HELP_MESSAGE)

    def wallet_command(self, update: Update, context: CallbackContext):
        """Wallet-Befehl Handler"""
        address = self.wallet_manager.get_address()
        if not address:
            update.message.reply_text(
                "❌ Keine Wallet verbunden. Bitte zuerst eine Wallet verbinden.",
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔗 Wallet verbinden", callback_data="connect_wallet")
                ]])
            )
            return

        balance = self.wallet_manager.get_balance()
        update.message.reply_text(
            format_wallet_info(balance, address),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💸 Senden", callback_data="send_sol")],
                [InlineKeyboardButton("📥 Empfangen", callback_data="receive_sol")]
            ])
        )

    def trade_command(self, update: Update, context: CallbackContext):
        """Trade-Befehl Handler"""
        if not self.wallet_manager.get_address():
            update.message.reply_text("❌ Bitte zuerst Wallet verbinden!")
            return

        active_signals = self.signal_processor.get_active_signals()
        if not active_signals:
            update.message.reply_text("🔍 Aktuell keine aktiven Trading Signale verfügbar.")
            return

        for idx, signal in enumerate(active_signals):
            message = create_trade_message(signal)
            update.message.reply_text(
                message,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("✅ Trade ausführen", callback_data=f"execute_trade_{idx}"),
                        InlineKeyboardButton("❌ Ignorieren", callback_data=f"ignore_trade_{idx}")
                    ]
                ])
            )

    def button_handler(self, update: Update, context: CallbackContext):
        """Callback Query Handler für Buttons"""
        query = update.callback_query
        query.answer()

        if query.data == "connect_wallet":
            # Wallet-Verbindung Logik
            public_key, private_key = self.wallet_manager.create_wallet()
            query.message.reply_text(
                f"✅ Neue Wallet erstellt!\n\nAdresse: {public_key}\n\n⚠️ Bitte Private Key sicher aufbewahren!"
            )

        elif query.data.startswith("execute_trade_"):
            signal_id = int(query.data.split("_")[-1])
            query.message.reply_text(
                "💰 Bitte Handelsbetrag in SOL eingeben:",
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("0.1 SOL", callback_data=f"amount_0.1_{signal_id}"),
                        InlineKeyboardButton("0.5 SOL", callback_data=f"amount_0.5_{signal_id}"),
                        InlineKeyboardButton("1.0 SOL", callback_data=f"amount_1.0_{signal_id}")
                    ]
                ])
            )

    def execute_trade(self, update: Update, context: CallbackContext, amount: float, signal_id: int):
        """Führt einen Trade aus"""
        try:
            signal = self.signal_processor.get_active_signals()[signal_id]
            success, tx_id = self.dex_connector.execute_trade(
                self.wallet_manager,
                signal['pair'],
                amount,
                signal['direction'] == 'long'
            )

            if success:
                self.signal_processor.mark_signal_executed(signal_id)
                update.callback_query.message.reply_text(
                    f"✅ Trade erfolgreich ausgeführt!\n\nBetrag: {amount} SOL\nTransaktion: {tx_id}"
                )
            else:
                update.callback_query.message.reply_text(
                    f"❌ Trade fehlgeschlagen: {tx_id}"
                )

        except Exception as e:
            logger.error(f"Fehler bei Trade-Ausführung: {e}")
            update.callback_query.message.reply_text(
                "❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es später erneut."
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
            dp.add_handler(CommandHandler("trade", self.trade_command))

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
    bot = TradingBot()
    bot.run()