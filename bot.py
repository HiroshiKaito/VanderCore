import logging
import json
from datetime import datetime
import pytz
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext, CallbackQueryHandler, MessageHandler, Filters
from telegram.utils.request import Request
from telegram.error import (TelegramError, Unauthorized, BadRequest,
                          TimedOut, ChatMigrated, NetworkError)
import config
from wallet_manager import WalletManager
from dex_connector import DexConnector
from signal_processor import SignalProcessor
from chart_analyzer import ChartAnalyzer
from automated_signal_generator import AutomatedSignalGenerator
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd
from typing import Dict, Any
import telegram
import urllib3
import certifi

# Konfiguriere sichere HTTPS-Verbindungen
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Update the logging configuration to capture more details
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    level=logging.DEBUG,  # Temporär auf DEBUG gesetzt für mehr Details
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        """Initialisiere den Bot"""
        try:
            logger.info("=== Starte Bot-Initialisierung ===")

            # Konfiguration laden und überprüfen
            self.config = config
            logger.debug(f"Admin User ID konfiguriert: {self.config.ADMIN_USER_ID}")
            logger.debug("Telegram Token vorhanden: " + ("Ja" if self.config.TELEGRAM_TOKEN else "Nein"))
            logger.debug(f"Token Länge: {len(self.config.TELEGRAM_TOKEN) if self.config.TELEGRAM_TOKEN else 0}")

            if not self.config.TELEGRAM_TOKEN:
                raise ValueError("Telegram Token nicht gefunden!")

            # Basis-Attribute
            self.maintenance_mode = False
            self.update_in_progress = False
            self.active_users = set()
            self.pending_operations = {}
            self.user_timezones = {}  # Speichert Zeitzonen pro Benutzer

            # Konfiguriere Request für optimale Verbindung
            request = Request(
                con_pool_size=8,
                connect_timeout=30.0,
                read_timeout=30.0,
                write_timeout=30.0,
                retry_on_timeout=True,
                maximum_retries=3
            )

            # Initialisiere Telegram Updater mit angepassten Einstellungen
            logger.info("Initialisiere Telegram Updater...")
            try:
                self.updater = Updater(
                    token=self.config.TELEGRAM_TOKEN,
                    use_context=True,
                    request_kwargs={
                        'read_timeout': 30,
                        'connect_timeout': 30,
                        'write_timeout': 30,
                        'pool_timeout': 30,
                        'cert': certifi.where(),  # Explizit SSL-Zertifikate konfigurieren
                        'verify': True,  # SSL-Verifizierung aktivieren
                        'proxy_url': None,  # Optional: Proxy-URL hier einfügen wenn nötig
                    },
                    request=request
                )

                if not self.updater:
                    raise ValueError("Updater konnte nicht initialisiert werden")

                # Teste Bot-Verbindung
                me = self.updater.bot.get_me()
                logger.info(f"Bot-Verbindung erfolgreich. Bot-Name: {me.first_name}, Bot-ID: {me.id}")

            except telegram.error.InvalidToken as token_error:
                logger.error(f"Ungültiger Telegram Token: {token_error}")
                raise ValueError("Der Telegram Token ist ungültig. Bitte überprüfen Sie den Token.")
            except telegram.error.NetworkError as network_error:
                logger.error(f"Netzwerkfehler bei Telegram-Verbindung: {network_error}")
                raise ValueError("Konnte keine Verbindung zu Telegram herstellen. Bitte überprüfen Sie Ihre Internetverbindung.")
            except Exception as updater_error:
                logger.error(f"Unerwarteter Fehler bei Telegram Updater Initialisierung: {updater_error}")
                raise

            # Komponenten
            logger.info("Initialisiere Wallet Manager...")
            self.wallet_manager = WalletManager(self.config.SOLANA_RPC_URL)

            logger.info("Initialisiere DEX Connector...")
            self.dex_connector = DexConnector()

            logger.info("Initialisiere Signal Processor...")
            self.signal_processor = SignalProcessor()

            # Initialisiere Chart Analyzer
            logger.info("Initialisiere Chart Analyzer...")
            self.chart_analyzer = ChartAnalyzer()

            # Initialisiere und starte Signal Generator
            logger.info("Initialisiere Signal Generator...")
            self.signal_generator = AutomatedSignalGenerator(
                self.dex_connector,
                self.signal_processor,
                self
            )

            # Lade gespeicherten Zustand
            self.load_state()
            logger.info("Bot-Zustand erfolgreich geladen")

            # Registriere Handler
            self._setup_handlers()

            # Starte Signal Generator wenn es aktive Nutzer gibt
            if self.active_users:
                logger.info(f"Starte Signal Generator für {len(self.active_users)} aktive Nutzer...")
                self.signal_generator.start()

            logger.info("Bot erfolgreich initialisiert")

        except Exception as e:
            logger.error(f"Kritischer Fehler bei Bot-Initialisierung: {e}")
            raise

    def run(self):
        """Startet den Bot"""
        try:
            logger.info("Starte Bot...")

            # Prüfe ob Updater initialisiert wurde
            if not self.updater:
                raise ValueError("Updater wurde nicht korrekt initialisiert")

            # Starte Polling mit zusätzlichen Debug-Informationen
            logger.info("Starte Polling...")
            self.updater.start_polling(
                timeout=30,
                read_latency=5,
                drop_pending_updates=True,
                allowed_updates=Update.ALL_TYPES
            )
            logger.info("Polling erfolgreich gestartet")

            # Warte auf Beenden
            logger.info("Bot läuft und wartet auf Nachrichten")
            self.updater.idle()

        except Exception as e:
            logger.error(f"Kritischer Fehler beim Starten des Bots: {e}")
            raise

    def _setup_handlers(self):
        """Registriert alle Command und Message Handler"""
        try:
            dp = self.updater.dispatcher

            # Command Handler
            dp.add_handler(CommandHandler("start", self.start))
            dp.add_handler(CommandHandler("hilfe", self.help_command))
            dp.add_handler(CommandHandler("wallet", self.wallet_command))
            dp.add_handler(CommandHandler("senden", self.send_command))
            dp.add_handler(CommandHandler("empfangen", self.receive_command))
            dp.add_handler(CommandHandler("trades", self.handle_trades_command))
            dp.add_handler(CommandHandler("wartung_start", self.enter_maintenance_mode))
            dp.add_handler(CommandHandler("wartung_ende", self.exit_maintenance_mode))
            dp.add_handler(CommandHandler("test_signal", self.test_signal))

            # Button Handler
            dp.add_handler(CallbackQueryHandler(self.button_handler))

            # Allgemeiner Message Handler
            dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_text))

            # Error Handler
            dp.add_error_handler(self.error_handler)

            logger.info("Handler erfolgreich registriert")

        except Exception as e:
            logger.error(f"Fehler beim Setup der Handler: {e}")
            raise

    def start(self, update: Update, context: CallbackContext):
        """Handler für den /start Befehl"""
        user_id = update.effective_user.id
        logger.info(f"Start-Befehl von User {user_id}")

        try:
            # Setze Standardzeitzone oder erkenne sie automatisch
            if str(user_id) not in self.user_timezones:
                timezone = self._detect_user_timezone(update.effective_user)
                self.user_timezones[str(user_id)] = timezone
                self.save_state()
                logger.info(f"Zeitzone für User {user_id} auf {timezone} gesetzt")

            logger.debug(f"Sende Start-Nachricht an User {user_id}")
            update.message.reply_text(
                "👋 Hey! Ich bin Dexter - der beste Solana Trading Bot auf dem Markt!\n\n"
                "Ich werde dir beim Trading helfen und:\n"
                "✅ Trading Signale mit KI-Analyse generieren\n"
                "✅ Risk Management überwachen\n"
                "✅ Dein Portfolio tracken\n"
                "✅ Marktanalysen durchführen\n\n"
                "Verfügbare Befehle:\n"
                "/wallet - Wallet-Verwaltung\n"
                "/trades - Aktive Trades anzeigen\n"
                "/hilfe - Weitere Hilfe anzeigen\n\n"
                "Ready to trade? 🎬",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Let's go! 🚀", callback_data="start_signal_search")]
                ])
            )
            logger.info(f"Start-Nachricht erfolgreich an User {user_id} gesendet")

        except Exception as e:
            logger.error(f"Fehler beim Start-Command: {e}")
            update.message.reply_text("❌ Es ist ein Fehler aufgetreten. Bitte versuche es später erneut.")

    def help_command(self, update: Update, context: CallbackContext):
        """Handler für den /hilfe Befehl"""
        update.message.reply_text(
            "🤖 Trading Bot Hilfe\n\n"
            "🔹 Basis Befehle:\n"
            "/start - Bot neu starten\n"
            "/hilfe - Diese Hilfe anzeigen\n\n"
            "🔹 Wallet Befehle:\n"
            "/wallet - Wallet-Status anzeigen\n"
            "/senden - Token senden\n"
            "/empfangen - Einzahlungsadresse anzeigen\n\n"
            "🔹 Trading Befehle:\n"
            "/trades - Aktuelle Trades anzeigen\n"
            "❓ Brauchen Sie Hilfe? Nutzen Sie /start um neu zu beginnen!"
        )

    def wallet_command(self, update: Update, context: CallbackContext):
        """Handler für den /wallet Befehl"""
        user_id = update.effective_user.id
        try:
            balance = self.wallet_manager.get_balance()
            update.message.reply_text(
                f"💰 Wallet Status\n\n"
                f"Aktuelles Guthaben: {balance:.4f} SOL\n\n"
                f"Was möchten Sie tun?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💸 Senden", callback_data="send_tokens"),
                     InlineKeyboardButton("📥 Empfangen", callback_data="receive_tokens")],
                    [InlineKeyboardButton("📊 Transaktionshistorie", callback_data="show_history")]
                ])
            )
        except Exception as e:
            logger.error(f"Fehler beim Wallet-Command: {e}")
            update.message.reply_text("❌ Fehler beim Abrufen des Wallet-Status")

    def send_command(self, update: Update, context: CallbackContext):
        """Handler für den /senden Befehl"""
        update.message.reply_text(
            "💸 Token senden\n\n"
            "Bitte geben Sie die Empfängeradresse und den Betrag ein:\n"
            "Format: <adresse> <betrag>\n"
            "Beispiel: 7fUAJdStEuGbc3sM84cKRL7pYYYCUp3KHLKGmrMjDrmP 1.5"
        )

    def receive_command(self, update: Update, context: CallbackContext):
        """Handler für den /empfangen Befehl"""
        try:
            wallet_address = self.wallet_manager.get_deposit_address()
            update.message.reply_text(
                f"📥 Einzahlungsadresse\n\n"
                f"`{wallet_address}`\n\n"
                f"Senden Sie SOL an diese Adresse.",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.error(f"Fehler beim Empfangen-Command: {e}")
            update.message.reply_text("❌ Fehler beim Abrufen der Einzahlungsadresse")

    def handle_trades_command(self, update: Update, context: CallbackContext) -> None:
        """Handler für den /trades Befehl - zeigt aktuelle Trades"""
        try:
            executed_signals = self.signal_processor.get_executed_signals()

            if not executed_signals:
                update.message.reply_text("📊 Keine aktiven Trades\n\n")
                return

            for idx, trade in enumerate(executed_signals):
                user_timezone = self.user_timezones.get(str(update.effective_user.id), 'UTC')
                localized_datetime = datetime.fromtimestamp(trade['timestamp']).astimezone(pytz.timezone(user_timezone))
                trade_message = (
                    f"🔄 Aktiver Trade #{idx + 1}\n\n"
                    f"Pair: {trade['pair']}\n"
                    f"Position: {'📈 LONG' if trade['direction'] == 'long' else '📉 SHORT'}\n"
                    f"Einstieg: {trade['entry']:.2f} USDC\n"
                    f"Stop Loss: {trade['stop_loss']:.2f} USDC\n"
                    f"Take Profit: {trade['take_profit']:.2f} USDC\n"
                    f"Erwarteter Profit: {trade['expected_profit']:.1f}%\n\n"
                    f"⏰ Eröffnet: {localized_datetime.strftime('%d.%m.%Y %H:%M:%S %Z%z')}"
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

    def button_handler(self, update: Update, context: CallbackContext):
        """Handler für Button-Callbacks"""
        query = update.callback_query
        user_id = query.from_user.id

        try:
            query.answer()  # Bestätige den Button-Click

            # Existierende Button-Handler...
            if query.data == "start_signal_search":
                logger.info(f"Signal-Suche aktiviert von User {user_id}")
                try:
                    # Füge Benutzer zu aktiven Nutzern hinzu
                    self.active_users.add(user_id)
                    self.save_state()  # Speichere aktive Nutzer
                    logger.info(f"User {user_id} zu aktiven Nutzern hinzugefügt")

                    # Starte Signal Generator falls noch nicht aktiv
                    if not self.signal_generator.is_running:
                        logger.info("Starte Signal Generator...")
                        self.signal_generator.start()
                        logger.info("Signal Generator erfolgreich gestartet")

                    # Bestätige die Aktivierung
                    query.message.reply_text(
                        "✨ Perfect! Ich suche jetzt aktiv nach den besten Trading-Gelegenheiten für dich.\n\n"
                        "Du erhältst automatisch eine Nachricht, sobald ich ein hochwertiges Signal gefunden habe.\n\n"
                        "Status: 🟢 Signal Generator aktiv"
                    )

                except Exception as e:
                    logger.error(f"Detaillierter Fehler beim Starten des Signal Generators: {str(e)}")
                    query.message.reply_text(
                        "❌ Fehler beim Aktivieren der Signal-Suche.\n"
                        "Bitte versuchen Sie es später erneut."
                    )

            elif query.data == "send_tokens":
                self.send_command(update, context)
            elif query.data == "receive_tokens":
                self.receive_command(update, context)
            elif query.data == "show_history":
                query.message.reply_text("📊 Transaktionshistorie wird geladen...")
            elif query.data == "trade_signal_new":
                query.message.reply_text("✅ Signal wird verarbeitet...")
            elif query.data == "ignore_signal":
                query.message.reply_text("❌ Signal ignoriert")
            elif query.data == "show_analysis":
                query.message.reply_text("📊 Detailanalyse wird geladen...")
            elif query.data == "show_chart":
                query.message.reply_text("📈 Chart wird hier angezeigt...")

        except Exception as e:
            logger.error(f"Fehler im Button Handler: {str(e)}")
            query.message.reply_text(
                "❌ Es ist ein Fehler aufgetreten.\n"
                f"Details: {str(e)}\n"
                "Bitte versuchen Sie es erneut."
            )

    def handle_text(self, update: Update, context: CallbackContext):
        """Handler für normale Textnachrichten"""
        user_id = update.effective_user.id
        text = update.message.text

        if self.maintenance_mode and str(user_id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text(
                "🛠️ Der Bot befindet sich aktuell im Wartungsmodus.\n"
                "Bitte versuchen Sie es später erneut."
            )
            return

        command = text.split()[0] if text else None
        self.handle_command(update, context)

    def handle_command(self, update: Update, context: CallbackContext):
        """Zentrale Command-Verarbeitung"""
        command = update.message.text.split()[0]

        if command == '/start':
            self.start(update, context)
        elif command == '/hilfe':
            self.help_command(update, context)
        elif command == '/wallet':
            self.wallet_command(update, context)
        elif command == '/senden':
            self.send_command(update, context)
        elif command == '/empfangen':
            self.receive_command(update, context)
        elif command == '/trades':
            self.handle_trades_command(update, context)
        elif command == '/wartung_start' and str(update.effective_user.id) == str(self.config.ADMIN_USER_ID):
            self.enter_maintenance_mode(update, context)
        elif command == '/wartung_ende' and str(update.effective_user.id) == str(self.config.ADMIN_USER_ID):
            self.exit_maintenance_mode(update, context)
        elif command == '/test_signal' and str(update.effective_user.id) == str(self.config.ADMIN_USER_ID):
            self.test_signal(update, context)
        else:
            self.handle_text(update, context)

    def save_state(self):
        """Speichert den Bot-Zustand"""
        try:
            state = {
                'active_users': list(self.active_users),
                'pending_operations': self.pending_operations,
                'signals': self.signal_processor.get_active_signals(),
                'user_timezones': self.user_timezones,  # Speichere Zeitzonen
                'timestamp': datetime.now().isoformat()
            }

            with open('bot_state.json', 'w') as f:
                json.dump(state, f)

            logger.info("Bot-Zustand erfolgreich gespeichert")

        except Exception as e:
            logger.error(f"Fehler beim Speichern des Bot-Zustands: {e}")

    def load_state(self):
        """Lädt den gespeicherten Bot-Zustand"""
        try:
            with open('bot_state.json', 'r') as f:
                state = json.load(f)

                self.active_users = set(state.get('active_users', []))
                self.pending_operations = state.get('pending_operations', {})
                self.user_timezones = state.get('user_timezones', {})  # Lade Zeitzonen

                # Stelle aktive Signale wieder her
                for signal in state.get('signals', []):
                    self.signal_processor.add_signal(signal)

                logger.info("Bot-Zustand erfolgreich geladen")

        except FileNotFoundError:
            logger.info("Keine Bot-Zustandsdatei gefunden, starte mit leerem Zustand")
        except Exception as e:
            logger.error(f"Fehler beim Laden des Bot-Zustands: {e}")

    def _detect_user_timezone(self, user: telegram.User) -> str:
        """Erkennt die wahrscheinliche Zeitzone des Nutzers basierend auf seinem Language Code"""
        try:
            # Zeitzonenzuordnung basierend auf Language Code
            timezone_mapping = {
                'de': 'Europe/Berlin',  # Deutschland
                'en': 'America/New_York',  # USA
                'fr': 'Europe/Paris',  # Frankreich
                'es': 'Europe/Madrid',  # Spanien
                'it': 'Europe/Rome',  # Italien
                'ru': 'Europe/Moscow',  # Russland
                'ja': 'Asia/Tokyo',  # Japan
                'zh': 'Asia/Shanghai',  # China
            }

            # Hole Language Code vom Nutzer
            lang_code = user.language_code if user.language_code else 'de'
            lang_code = lang_code.split('-')[0].lower()  # Extrahiere Basis-Sprachcode (z.B. 'en-US' -> 'en')

            # Wähle Zeitzone basierend auf Sprache
            timezone_name = timezone_mapping.get(lang_code, 'Europe/Berlin')
            logger.info(f"Erkannte Zeitzone für User {user.id} (Sprache: {lang_code}): {timezone_name}")

            return timezone_name

        except Exception as e:
            logger.error(f"Fehler bei Zeitzonenerkennung: {e}")
            return 'Europe/Berlin'  # Fallback auf Standardzeitzone

    def format_timestamp(self, timestamp, user_id):
        """Formatiert einen Zeitstempel in der Zeitzone des Benutzers"""
        try:
            user_tz = self.user_timezones.get(str(user_id), 'Europe/Berlin')
            logger.debug(f"Formatiere Zeit für User {user_id} in Zeitzone {user_tz}")

            try:
                timezone = pytz.timezone(user_tz)
                dt = datetime.fromtimestamp(timestamp, pytz.UTC)
                local_dt = dt.astimezone(timezone)
                formatted_time = local_dt.strftime('%d.%m.%Y %H:%M:%S %Z')

                logger.debug(f"Zeitumwandlung: UTC {dt} -> Lokal {local_dt}")
                return formatted_time

            except pytz.exceptions.UnknownTimeZoneError:
                logger.error(f"Unbekannte Zeitzone: {user_tz}, verwende UTC")
                return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M:%S UTC')

        except Exception as e:
            logger.error(f"Fehler bei der Zeitformatierung: {e}")
            return datetime.fromtimestamp(timestamp).strftime('%d.%m.%Y %H:%M:%S')

    def enter_maintenance_mode(self, update: Update, context: CallbackContext):
        """Aktiviert den Wartungsmodus"""
        if str(update.effective_user.id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text("❌ Keine Berechtigung")
            return

        self.maintenance_mode = True
        update.message.reply_text("🛠️ Wartungsmodus aktiviert")

    def exit_maintenance_mode(self, update: Update, context: CallbackContext):
        """Deaktiviert den Wartungsmodus"""
        if str(update.effective_user.id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text("❌ Keine Berechtigung")
            return

        self.maintenance_mode = False
        update.message.reply_text("✅ Wartungsmodus deaktiviert")

    def test_signal(self, update: Update, context: CallbackContext):
        """Testet die Signalverarbeitung"""
        if str(update.effective_user.id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text("❌ Keine Berechtigung")
            return
        try:
            # Simuliere ein Signal
            test_signal = {
                'pair': 'SOL/USDC',
                'direction': 'long',
                'entry': 25.50,
                'stop_loss': 24.00,
                'take_profit': 27.00,
                'timestamp': datetime.now().timestamp()
            }
            self.signal_processor.add_signal(test_signal)
            update.message.reply_text("✅ Testsignal hinzugefügt")
        except Exception as e:
            logger.error(f"Fehler beim Testsignal: {e}")
            update.message.reply_text("❌ Fehler beim Hinzufügen des Testsignals")

    def error_handler(self, update: Update, context: CallbackContext):
        """Globaler Error Handler"""
        logger.error(f"Update {update} verursachte Fehler {context.error}")
        try:
            if update.effective_message:
                update.effective_message.reply_text(
                    "❌ Es ist ein Fehler aufgetreten.\n"
                    "Bitte versuchen Sie es später erneut."
                )
        except Exception as e:
            logger.error(f"Fehler beim Senden der Fehlermeldung: {e}")


if __name__ == "__main__":
    try:
        logger.info("=== Starte Solana Trading Bot ===")
        bot = TelegramBot()
        logger.info("Bot-Instanz erfolgreich erstellt")
        bot.run()
    except Exception as e:
        logger.error(f"=== Kritischer Fehler beim Starten des Bots: {e} ===")
        raise