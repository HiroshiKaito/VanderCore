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
    level=logging.DEBUG  # Ändern auf DEBUG für mehr Details
)
logger = logging.getLogger(__name__)

class SolanaWalletBot:
    def __init__(self):
        """Initialisiert den Bot mit Konfiguration"""
        logger.info("Initialisiere Bot...")
        self.config = Config()

        if not self.config.TELEGRAM_TOKEN:
            logger.error("TELEGRAM_TOKEN nicht gefunden!")
            raise ValueError("TELEGRAM_TOKEN muss gesetzt sein!")

        self.wallet_manager = WalletManager(self.config.SOLANA_RPC_URL)
        self.updater = None
        self.waiting_for_address = {}
        self.waiting_for_trade_amount = False # Added to track trade amount input

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
            "/senden - SOL senden (mit QR-Scanner oder manueller Eingabe)\n"
            "/empfangen - Einzahlungsadresse als QR-Code anzeigen\n\n"
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

    def button_handler(self, update: Update, context: CallbackContext) -> None:
        """Callback Query Handler für Buttons"""
        query = update.callback_query
        user_id = query.from_user.id
        logger.info(f"Button-Callback von User {user_id}: {query.data}")

        try:
            query.answer()

            if query.data.startswith("confirm_send_"):
                _, _, address, amount = query.data.split("_")
                amount = float(amount)

                # Führe die Transaktion aus
                logger.info(f"Führe Transaktion aus: {amount} SOL an {address}")
                success, result = self.wallet_manager.send_sol(address, amount)

                if success:
                    query.message.reply_text(
                        f"✅ Transaktion erfolgreich!\n\n"
                        f"Betrag: {format_amount(amount)} SOL\n"
                        f"An: `{address}`\n"
                        f"Transaktion: `{result}`",
                        parse_mode='Markdown'
                    )
                    logger.info(f"Transaktion erfolgreich: {result}")
                else:
                    query.message.reply_text(f"❌ Fehler bei der Transaktion: {result}")
                    logger.error(f"Transaktionsfehler: {result}")

            elif query.data == "cancel_send":
                query.message.reply_text("❌ Transaktion abgebrochen")
                logger.info(f"Transaktion abgebrochen von User {user_id}")

            elif query.data == "create_wallet":
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
                        f"Er wird benötigt, um auf Ihre Wallet zuzugreifen.",
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
                logger.debug(f"User {user_id} wählt manuelle Adresseingabe")
                self.waiting_for_address[user_id] = True
                query.message.reply_text(
                    "✍️ Bitte geben Sie die Empfängeradresse und den Betrag im Format ein:\n"
                    "ADRESSE BETRAG\n\n"
                    "Beispiel:\n"
                    "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU 0.1"
                )
                logger.debug(f"Warte auf Adresseingabe von User {user_id}")

            elif query.data.startswith("trade_signal_"): #Handles new trading signals
                _, _, signal_index = query.data.split("_")
                signal_index = int(signal_index)
                self.waiting_for_trade_amount = True #Set to true before asking for amount
                query.message.reply_text(
                    "💰 Wie viel SOL möchten Sie für diesen Trade einsetzen?\n\n"
                    "Bitte geben Sie den Betrag in SOL ein (z.B. 0.5):"
                )

            elif query.data == "ignore_signal": #Handles ignoring signals
                query.message.reply_text("Signal wurde ignoriert. Sie erhalten weiterhin neue Signale.")

            elif query.data.startswith("confirm_trade_"):
                _, _, amount_str = query.data.split("_")
                amount = float(amount_str)
                # Add your trading logic here using amount and signal data
                query.message.reply_text(f"Trade mit {amount} SOL wird ausgeführt.")

            elif query.data == "cancel_trade":
                query.message.reply_text("Trade abgebrochen.")
            elif query.data == "start_signal_search":
                query.message.reply_text(
                    "✨ Perfect! Ich suche jetzt aktiv nach den besten Trading-Gelegenheiten für dich.\n\n"
                    "Du erhältst automatisch eine Nachricht, sobald ich ein hochwertiges Signal gefunden habe.\n"
                    "Die Signale kannst du auch jederzeit mit /signal abrufen."
                )

        except Exception as e:
            logger.error(f"Fehler im Button Handler: {e}")

    def handle_text(self, update: Update, context: CallbackContext) -> None:
        """Verarbeitet Textnachrichten für manuelle Adresseingabe und Trade-Beträge"""
        user_id = update.effective_user.id
        logger.debug(f"Textnachricht von User {user_id} empfangen")

        if user_id not in self.waiting_for_address and not self.waiting_for_trade_amount:
            logger.debug(f"User {user_id} ist nicht im Eingabe-Modus")
            return

        try:
            text = update.message.text.strip()
            logger.debug(f"Verarbeite Eingabe: {text}")

            if self.waiting_for_trade_amount: #Handles trade amount input
                try:
                    amount = float(text)
                    balance = self.wallet_manager.get_balance()

                    if amount <= 0:
                        update.message.reply_text("❌ Bitte geben Sie einen positiven Betrag ein.")
                        return

                    if amount > balance:
                        update.message.reply_text(
                            f"❌ Nicht genügend Guthaben!\n\n"
                            f"Verfügbar: {balance:.4f} SOL\n"
                            f"Benötigt: {amount:.4f} SOL"
                        )
                        return

                    # Zeige Zusammenfassung und frage nach Bestätigung
                    update.message.reply_text(
                        f"📝 Trade-Zusammenfassung:\n\n"
                        f"Betrag: {amount:.4f} SOL\n"
                        f"Verbleibendes Guthaben: {(balance - amount):.4f} SOL\n\n"
                        f"Möchten Sie den Trade ausführen?",
                        reply_markup=InlineKeyboardMarkup([
                            [
                                InlineKeyboardButton("✅ Bestätigen", callback_data=f"confirm_trade_{amount}"),
                                InlineKeyboardButton("❌ Abbrechen", callback_data="cancel_trade")
                            ]
                        ])
                    )

                except ValueError:
                    update.message.reply_text("❌ Ungültiger Betrag. Bitte geben Sie eine Zahl ein.")
                finally:
                    self.waiting_for_trade_amount = False

            elif user_id in self.waiting_for_address: #Handle address input
                parts = text.split()

                if len(parts) != 2:
                    update.message.reply_text(
                        "❌ Falsches Format! Bitte geben Sie die Adresse und den Betrag so ein:\n"
                        "ADRESSE BETRAG\n\n"
                        "Beispiel:\n"
                        "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU 0.1"
                    )
                    return

                address, amount_str = parts
                logger.debug(f"Parsed: Adresse={address}, Betrag={amount_str}")

                # Validiere den Betrag
                valid, amount = validate_amount(amount_str)
                if not valid:
                    update.message.reply_text("❌ Ungültiger Betrag! Bitte geben Sie eine positive Zahl ein.")
                    return

                # Schätze Transaktionsgebühren
                fee = self.wallet_manager.estimate_transaction_fee()
                total_amount = amount + fee

                # Führe Sicherheits- und Risikoanalyse durch
                security_score, security_warnings = self.wallet_manager.security_analyzer.analyze_wallet_security(
                    address, self.wallet_manager.transaction_history
                )
                risk_score, risk_recommendations = self.wallet_manager.risk_analyzer.analyze_transaction_risk(
                    amount, self.wallet_manager.transaction_history
                )

                # Erstelle detaillierte Transaktionsinfo
                security_status = "🟢 Sicher" if security_score >= 70 else "🟡 Prüfen" if security_score >= 50 else "🔴 Riskant"
                warnings_text = "\n".join(f"• {warning}" for warning in security_warnings) if security_warnings else "• Keine Warnungen"

                transaction_info = (
                    f"📝 Transaktionsdetails:\n\n"
                    f"An: `{address}`\n"
                    f"Betrag: {format_amount(amount)} SOL\n"
                    f"Gebühr: {format_amount(fee)} SOL\n"
                    f"Gesamt: {format_amount(total_amount)} SOL\n\n"
                    f"🛡 Sicherheitsbewertung: {security_status} ({security_score:.0f}/100)\n"
                    f"⚠️ Sicherheitshinweise:\n{warnings_text}\n\n"
                    f"📊 Risikoanalyse:\n{risk_recommendations}\n\n"
                    f"Möchten Sie die Transaktion ausführen?"
                )

                # Zeige Transaktionsdetails und frage nach Bestätigung
                update.message.reply_text(
                    transaction_info,
                    parse_mode='Markdown',
                    reply_markup=InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("✅ Ja", callback_data=f"confirm_send_{address}_{amount}"),
                            InlineKeyboardButton("❌ Nein", callback_data="cancel_send")
                        ]
                    ])
                )

        except Exception as e:
            logger.error(f"Fehler bei manueller Adresseingabe: {e}")
            update.message.reply_text("❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.")
        finally:
            # Entferne den User aus der Wartelist
            self.waiting_for_address.pop(user_id, None)
            logger.debug(f"User {user_id} aus Adresseingabe-Modus entfernt")


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
                # Erstelle eine formatierte Nachricht für jedes Signal
                signal_message = (
                    f"📊 Trading Signal #{idx + 1}\n\n"
                    f"Pair: {signal['pair']}\n"
                    f"Signal: {'📈 LONG' if signal['direction'] == 'long' else '📉 SHORT'}\n"
                    f"Einstieg: {format_amount(signal['entry'])} SOL\n"
                    f"Stop Loss: {format_amount(signal['stop_loss'])} SOL\n"
                    f"Take Profit: {format_amount(signal['take_profit'])} SOL\n\n"
                    f"📈 Trend: {signal['trend']} (Stärke: {signal['trend_strength']:.1f})\n"
                    f"💰 Erwarteter Profit: {signal['expected_profit']:.1f}%\n"
                    f"⚠️ Risiko-Score: {signal['risk_score']:.1f}\n"
                    f"✨ Signal-Qualität: {signal['signal_quality']}/10\n\n"
                    f"Möchten Sie dieses Signal handeln?"
                )

                # Erstelle Inline-Buttons für die Interaktion
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Handeln", callback_data=f"trade_signal_{idx}"),
                        InlineKeyboardButton("❌ Ignorieren", callback_data=f"ignore_signal")
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
            executed_signals = [s for s in self.signal_processor.active_signals
                                 if s['status'] == 'ausgeführt']

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
                    f"Einstieg: {format_amount(trade['entry'])} SOL\n"
                    f"Stop Loss: {format_amount(trade['stop_loss'])} SOL\n"
                    f"Take Profit: {format_amount(trade['take_profit'])} SOL\n"
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


    def run(self):
        """Startet den Bot"""
        logger.info("Starting bot...")
        try:
            # Initialize updater with bot's token
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

            # Add error handler
            dp.add_error_handler(self.error_handler)
            logger.debug("Error Handler registriert")

            # Command handlers
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