"""Main bot file for the Solana Trading Bot"""
import logging
import pytz
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
from datetime import datetime, timedelta
import json
import os
import time
import threading
from flask import Flask, jsonify
from config import Config
from wallet_manager import WalletManager
from utils import format_amount, validate_amount, format_wallet_info
from signal_processor import SignalProcessor
from dex_connector import DexConnector
from automated_signal_generator import AutomatedSignalGenerator
from apscheduler.schedulers.background import BackgroundScheduler
import pandas as pd

# Setze Werkzeug Logger auf WARNING
logging.getLogger('werkzeug').setLevel(logging.WARNING)

# Flask App für Replit
app = Flask(__name__)

# Logging Setup mit detailliertem Format
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

@app.route('/')
def home():
    return jsonify({"status": "Bot is running", "timestamp": datetime.now().isoformat()})

def run_flask():
    """Startet den Flask-Server im Hintergrund"""
    try:
        logger.info("Starte Flask-Server...")
        app.run(host='0.0.0.0', port=5000)
    except Exception as e:
        logger.error(f"Fehler beim Starten des Flask-Servers: {e}")
        raise

class SolanaWalletBot:
    def __init__(self):
        """Initialisiert den Bot mit Konfiguration"""
        try:
            logger.info("Initialisiere Bot...")
            self.config = Config()

            # Validiere Token
            if not self.config.TELEGRAM_TOKEN:
                raise ValueError("TELEGRAM_TOKEN nicht gefunden!")

            # Setze Timezone für APScheduler
            self.timezone = pytz.timezone('UTC')

            # Bot-Status
            self.maintenance_mode = False
            self.update_in_progress = False
            self.active_users = set()
            self.pending_operations = {}

            # Komponenten
            logger.info("Initialisiere Wallet Manager...")
            self.wallet_manager = WalletManager(self.config.SOLANA_RPC_URL)
            self.updater = None

            logger.info("Initialisiere DEX Connector...")
            self.dex_connector = DexConnector()

            logger.info("Initialisiere Signal Processor...")
            self.signal_processor = SignalProcessor()
            self.signal_generator = None

            logger.info("Bot erfolgreich initialisiert")

        except Exception as e:
            logger.error(f"Fehler bei Bot-Initialisierung: {e}")
            raise

    def enter_maintenance_mode(self, update: Update, context: CallbackContext):
        """Aktiviert den Wartungsmodus"""
        if str(update.effective_user.id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text("❌ Nur Administratoren können diese Aktion ausführen.")
            return

        self.maintenance_mode = True

        # Benachrichtige alle aktiven Nutzer
        maintenance_message = (
            "🔧 Wartungsarbeiten angekündigt!\n\n"
            "Der Bot wird in Kürze aktualisiert. "
            "Ihre offenen Trades und Signale bleiben erhalten.\n"
            "Wir informieren Sie, sobald die Wartung abgeschlossen ist."
        )

        success_count = 0
        failed_count = 0
        for active_user_id in self.active_users:
            try:
                context.bot.send_message(
                    chat_id=active_user_id,
                    text=maintenance_message,
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Fehler beim Senden der Wartungsnachricht an User {active_user_id}: {e}")
                failed_count += 1

        # Bestätige dem Admin die Aktivierung und sende Statistik
        status_message = (
            "✅ Wartungsmodus aktiviert\n\n"
            f"📊 Benachrichtigungen gesendet an:\n"
            f"- Erfolgreich: {success_count} Nutzer\n"
            f"- Fehlgeschlagen: {failed_count} Nutzer\n\n"
            "Neue Anfragen werden pausiert."
        )

        update.message.reply_text(status_message)
        logger.info("Wartungsmodus aktiviert")

    def exit_maintenance_mode(self, update: Update, context: CallbackContext):
        """Deaktiviert den Wartungsmodus"""
        if str(update.effective_user.id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text("❌ Nur Administratoren können diese Aktion ausführen.")
            return

        self.maintenance_mode = False

        # Benachrichtige alle aktiven Nutzer
        completion_message = (
            "✅ Wartungsarbeiten abgeschlossen!\n\n"
            "Der Bot ist wieder vollständig verfügbar.\n"
            "Alle Ihre Trades und Signale sind weiterhin aktiv."
        )

        success_count = 0
        failed_count = 0
        for active_user_id in self.active_users:
            try:
                context.bot.send_message(
                    chat_id=active_user_id,
                    text=completion_message,
                    parse_mode='Markdown'
                )
                success_count += 1
            except Exception as e:
                logger.error(f"Fehler beim Senden der Abschlussnachricht an User {active_user_id}: {e}")
                failed_count += 1

        # Bestätige dem Admin die Deaktivierung und sende Statistik
        status_message = (
            "✅ Wartungsmodus deaktiviert\n\n"
            f"📊 Benachrichtigungen gesendet an:\n"
            f"- Erfolgreich: {success_count} Nutzer\n"
            f"- Fehlgeschlagen: {failed_count} Nutzer\n\n"
            "Bot ist wieder voll verfügbar."
        )

        update.message.reply_text(status_message)
        logger.info("Wartungsmodus deaktiviert")

    def save_state(self):
        """Speichert den aktuellen Bot-Zustand"""
        try:
            state = {
                'active_users': list(self.active_users),
                'pending_operations': self.pending_operations,
                'signals': self.signal_processor.get_active_signals(),
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
            if os.path.exists('bot_state.json'):
                with open('bot_state.json', 'r') as f:
                    state = json.load(f)

                self.active_users = set(state.get('active_users', []))
                self.pending_operations = state.get('pending_operations', {})

                # Stelle aktive Signale wieder her
                for signal in state.get('signals', []):
                    self.signal_processor.process_signal(signal)

                logger.info("Bot-Zustand erfolgreich geladen")

        except Exception as e:
            logger.error(f"Fehler beim Laden des Bot-Zustands: {e}")

    def graceful_shutdown(self):
        """Führt einen kontrollierten Shutdown durch"""
        try:
            logger.info("Starte kontrollierten Shutdown...")

            # Speichere aktuellen Zustand
            self.save_state()

            # Stoppe Signal Generator
            if self.signal_generator:
                self.signal_generator.stop()
                logger.info("Signal Generator gestoppt")

            # Beende alle aktiven API-Verbindungen
            self.dex_connector.close()
            logger.info("DEX Verbindungen geschlossen")

            # Stoppe den Updater
            if self.updater:
                self.updater.stop()
                logger.info("Updater gestoppt")

            logger.info("Kontrollierter Shutdown abgeschlossen")

        except Exception as e:
            logger.error(f"Fehler beim kontrollierten Shutdown: {e}")

    def handle_update(self, update: Update, context: CallbackContext):
        """Zentrale Update-Behandlung mit Wartungsmodus-Check"""
        if not update.effective_user:
            logger.warning("Update ohne effektiven Benutzer empfangen")
            return

        user_id = update.effective_user.id
        logger.info(f"Update von User {user_id} empfangen")

        # Füge Nutzer zu aktiven Nutzern hinzu
        self.active_users.add(user_id)
        logger.debug(f"Aktive Nutzer aktualisiert: {len(self.active_users)} Nutzer")

        # Prüfe Wartungsmodus
        if self.maintenance_mode and str(user_id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text(
                "🔧 Der Bot befindet sich aktuell im Wartungsmodus.\n"
                "Bitte versuchen Sie es später erneut."
            )
            return

        # Normale Kommando-Verarbeitung
        if update.message:
            message = update.message.text
            if message:
                if message.startswith('/'):
                    self.handle_command(update, context)
                else:
                    self.handle_text(update, context)
        elif update.callback_query:
            self.button_handler(update, context)


    def error_handler(self, update: object, context: CallbackContext) -> None:
        """Verbesserte Fehlerbehandlung mit Auto-Recovery"""
        logger.error(f"Fehler aufgetreten: {context.error}")
        try:
            raise context.error
        except Conflict:
            logger.error("Konflikt mit anderer Bot-Instanz erkannt")
            self._attempt_recovery("conflict")
        except NetworkError:
            logger.error("Netzwerkfehler erkannt")
            self._attempt_recovery("network")
        except TelegramError as e:
            logger.error(f"Telegram API Fehler: {e}")
            self._attempt_recovery("telegram")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler: {e}")
            self._attempt_recovery("general")

    def _attempt_recovery(self, error_type: str, max_retries: int = 3) -> None:
        """Versucht den Bot nach einem Fehler wiederherzustellen"""
        retry_count = 0
        while retry_count < max_retries:
            try:
                logger.info(f"Recovery-Versuch {retry_count + 1}/{max_retries} für {error_type}")

                # Benachrichtige Admin über Recovery-Versuch
                self.notify_admin(
                    f"Recovery-Versuch {retry_count + 1}/{max_retries} für {error_type}",
                    is_critical=(retry_count == max_retries - 1)
                )

                # Speichere aktuellen Zustand
                self.save_state()

                if self.updater:
                    # Stoppe bestehende Verbindungen
                    self.updater.stop()

                    # Warte kurz
                    time.sleep(5)

                    # Starte Polling neu
                    self.updater.start_polling(drop_pending_updates=True)
                    logger.info("Bot erfolgreich neu gestartet")

                    # Erfolgreiche Recovery-Benachrichtigung
                    self.notify_admin(f"Recovery für {error_type} erfolgreich")
                    return

            except Exception as e:
                logger.error(f"Recovery-Versuch {retry_count + 1} fehlgeschlagen: {e}")
                retry_count += 1
                time.sleep(10 * retry_count)  # Exponentielles Backoff

        logger.critical(f"Recovery nach {max_retries} Versuchen fehlgeschlagen")
        self.notify_admin(
            f"KRITISCH: Recovery nach {max_retries} Versuchen fehlgeschlagen. "
            f"Manueller Eingriff erforderlich.",
            is_critical=True
        )

    def _send_heartbeat(self):
        """Sendet regelmäßige Heartbeat-Signale"""
        try:
            logger.debug("Heartbeat check...")
            if not self.updater or not self.updater.running:
                logger.warning("Bot nicht aktiv, starte Recovery")
                self.notify_admin("Heartbeat-Check fehlgeschlagen, starte Recovery", is_critical=True)
                self._attempt_recovery("heartbeat")
            else:
                logger.debug("Heartbeat OK")
        except Exception as e:
            logger.error(f"Heartbeat-Check fehlgeschlagen: {e}")
            self.notify_admin(f"Heartbeat-Check-Fehler: {e}", is_critical=True)

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

            if query.data.startswith("trade_signal_"):
                signal_idx = int(query.data.split("_")[-1])
                active_signals = self.signal_processor.get_active_signals()

                if signal_idx < len(active_signals):
                    signal = active_signals[signal_idx]
                    # Hier können Sie die Trading-Logik implementieren
                    confirmation_message = (
                        f"✅ Signal wird ausgeführt:\n\n"
                        f"Pair: {signal['pair']}\n"
                        f"Richtung: {'📈 LONG' if signal['direction'] == 'long' else '📉 SHORT'}\n"
                        f"Einstieg: {signal['entry']:.2f} USDC"
                    )
                    query.message.reply_text(confirmation_message)
                    logger.info(f"User {user_id} führt Signal #{signal_idx} aus")

            elif query.data.startswith("ignore_signal_"):
                signal_idx = int(query.data.split("_")[-1])
                query.message.delete()
                logger.info(f"Signal-Nachricht wurde auf Benutzeranfrage gelöscht")
                return

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
                        f"⚠️ WICHTIG: Bewahren Sie den Private Key sicher auf!",
                        parse_mode='Markdown'
                    )

                    # Füge den Benutzer zu aktiven Nutzern hinzu
                    self.active_users.add(user_id)
                    logger.info(f"User {user_id} zu aktiven Nutzern hinzugefügt")

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
                # Initialisiere und starte den Signal Generator
                if not self.signal_generator:
                    logger.info("Initialisiere Signal Generator...")
                    self.signal_generator = AutomatedSignalGenerator(
                        self.dex_connector,
                        self.signal_processor,
                        self
                    )
                    self.signal_generator.start()
                    logger.info("Signal Generator erfolgreich gestartet")

                # Bestätige die Aktivierung der Signal-Suche
                query.message.reply_text(
                    "✨ Perfect! Ich suche jetzt aktiv nach den besten Trading-Gelegenheiten für dich.\n\n"
                    "Du erhältst automatisch eine Nachricht, sobald ich ein hochwertiges Signal gefunden habe.\n"
                    "Die Signale kannst du auch jederzeit mit /signal abrufen."
                )
                logger.info(f"Signal-Suche für User {user_id} aktiviert")

            elif query.data == "ignore_signal":
                query.message.delete()
                logger.info(f"Signal-Nachricht wurde auf Benutzeranfrage gelöscht")
                return

            elif query.data == "trade_signal_new":
                query.message.reply_text(
                    "✅ Signal wird ausgeführt...\n"
                    "Sie erhalten eine Bestätigung, sobald der Trade platziert wurde."
                )
                logger.info(f"User {query.from_user.id} führt neues Signal aus")

        except Exception as e:
            logger.error(f"Fehler im Button Handler: {e}")
            query.message.reply_text("❌ Ein Fehler ist aufgetreten. Bitte versuchen Sie es erneut.")

    def handle_command(self, update: Update, context: CallbackContext):
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
        elif command == '/test_admin' and str(update.effective_user.id) == str(self.config.ADMIN_USER_ID):
            self.test_admin_notification(update, context)
        elif command == '/test_signal' and str(update.effective_user.id) == str(self.config.ADMIN_USER_ID):
            self.test_signal(update, context)
        else:
            self.handle_text(update, context)

    def test_signal(self, update: Update, context: CallbackContext):
        """Generiert ein Test-Signal"""
        try:
            user_id = update.effective_user.id
            logger.info(f"Test-Signal-Befehl empfangen von User {user_id}")

            # Bestätige den Empfang des Befehls an den Benutzer
            update.message.reply_text("🔄 Generiere Test-Signal...")

            # Erstelle ein Test-Signal
            test_signal = {
                'pair': 'SOL/USD',
                'direction': 'long',
                'entry': 145.50,
                'stop_loss': 144.50,
                'take_profit': 147.50,
                'timestamp': datetime.now().timestamp(),
                'token_address': "SOL",
                'expected_profit': 1.37,
                'signal_quality': 7.5,
                'trend_strength': 0.8,
            }

            logger.info(f"Test-Signal erstellt: {test_signal}")

            try:
                # Verarbeite das Signal
                logger.info("Verarbeite Test-Signal...")
                processed_signal = self.signal_processor.process_signal(test_signal)
                if processed_signal:
                    signal_message = (
                        f"🎯 Trading Signal erkannt!\n\n"
                        f"Pair: {processed_signal['pair']}\n"
                        f"Position: {'📈 LONG' if processed_signal['direction'] == 'long' else '📉 SHORT'}\n"
                        f"Entry: {processed_signal['entry']:.2f} USDC\n"
                        f"Stop Loss: {processed_signal['stop_loss']:.2f} USDC\n"
                        f"Take Profit: {processed_signal['take_profit']:.2f} USDC\n"
                        f"Erwarteter Profit: {processed_signal['expected_profit']:.1f}%\n"
                        f"Signal Qualität: {processed_signal['signal_quality']:.1f}/10\n"
                        f"Trend Stärke: {processed_signal['trend_strength']:.2f}"
                    )

                    keyboard = [
                        [
                            InlineKeyboardButton("✅ Signal handeln", callback_data="trade_signal_new"),
                            InlineKeyboardButton("❌ Ignorieren", callback_data="ignore_signal")
                        ]
                    ]

                    logger.info("Sende Test-Signal an Benutzer...")
                    update.message.reply_text(
                        signal_message,
                        reply_markup=InlineKeyboardMarkup(keyboard)
                    )
                    logger.info("Test-Signal erfolgreich gesendet")
                else:
                    logger.error("Signal konnte nicht verarbeitet werden")
                    update.message.reply_text("❌ Fehler bei der Signal-Verarbeitung")
            except Exception as process_error:
                logger.error(f"Fehler bei der Signal-Verarbeitung: {process_error}")
                update.message.reply_text("❌ Fehler bei der Signal-Verarbeitung. Bitte versuchen Sie es später erneut.")

        except Exception as e:
            logger.error(f"Fehler beim Generieren des Test-Signals: {e}")
            update.message.reply_text("❌ Fehler beim Generieren des Test-Signals")

    def notify_admin(self, message: str, is_critical: bool = False):
        """Sendet eine Benachrichtigung an den Admin als private Nachricht"""
        try:
            if not self.config.ADMIN_USER_ID:
                logger.error("Admin User ID nicht konfiguriert")
                return
            prefix = "🚨 KRITISCH" if is_critical else "ℹ️ INFO"
            admin_message = f"{prefix}: {message}\n\nZeitstempel: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

            if self.updater and self.updater.bot:
                # Sende die Nachricht direkt an den Admin-Chat
                self.updater.bot.send_message(
                    chat_id=self.config.ADMIN_USER_ID,
                    text=admin_message,
                    parse_mode='Markdown'
                )
                logger.info(f"Admin-Benachrichtigung gesendet: {message}")
            else:
                logger.error("Bot-Updater nicht verfügbar für Admin-Benachrichtigung")
        except Exception as e:
            logger.error(f"Fehler beim Senden der Admin-Benachrichtigung: {e}")


    def test_admin_notification(self, update: Update, context: CallbackContext):
        """Sendet eine Test-Benachrichtigung an den Admin"""
        if str(update.effective_user.id) != str(self.config.ADMIN_USER_ID):
            update.message.reply_text("❌ Nur Administratoren können diese Aktion ausführen.")
            return

        try:
            # Sende Test-Benachrichtigung
            self.notify_admin(
                "Dies ist eine Test-Benachrichtigung.\n"
                "So sehen Admin-Benachrichtigungen aus!",
                is_critical=False
            )

            # Sende auch eine kritische Test-Nachricht
            self.notify_admin(
                "Dies ist eine kritische Test-Benachrichtigung!",
                is_critical=True
            )

            update.message.reply_text("✅ Test-Benachrichtigungen wurden gesendet!")

        except Exception as e:
            logger.error(f"Fehler beim Senden der Test-Benachrichtigung: {e}")
            update.message.reply_text("❌ Fehler beim Senden der Test-Benachrichtigung")

    def run(self):
        """Startet den Bot"""
        try:
            logger.info("Starte Bot...")

            # Lade gespeicherten Zustand
            self.load_state()

            # Initialisiere Updater
            self.updater = Updater(token=self.config.TELEGRAM_TOKEN, use_context=True)
            dp = self.updater.dispatcher

            # Registriere Handler
            dp.add_handler(CommandHandler("start", self.start))
            dp.add_handler(CommandHandler("hilfe", self.help_command))
            dp.add_handler(CommandHandler("wallet", self.wallet_command))
            dp.add_handler(CommandHandler("senden", self.send_command))
            dp.add_handler(CommandHandler("empfangen", self.receive_command))
            dp.add_handler(CommandHandler("trades", self.handle_trades_command))
            dp.add_handler(CommandHandler("test_signal", self.test_signal))
            dp.add_handler(CommandHandler("wartung_start", self.enter_maintenance_mode))
            dp.add_handler(CommandHandler("wartung_ende", self.exit_maintenance_mode))

            # Füge Message Handler für Text-Nachrichten hinzu
            dp.add_handler(MessageHandler(Filters.text & ~Filters.command, self.handle_text))

            # Füge Callback Query Handler hinzu
            dp.add_handler(CallbackQueryHandler(self.button_handler))

            # Füge Error Handler hinzu
            dp.add_error_handler(self.error_handler)

            # Starte Flask im Hintergrund
            logger.info("Starte Flask-Server im Hintergrund...")
            flask_thread = threading.Thread(target=run_flask, daemon=True)
            flask_thread.start()

            # Warte kurz, damit Flask starten kann
            time.sleep(2)
            logger.info("Flask-Server gestartet")

            # Starte den Bot
            logger.info("Starte Telegram Bot Polling...")
            self.updater.start_polling(drop_pending_updates=True)
            logger.info("Bot erfolgreich gestartet!")

            # Warte auf Beenden
            self.updater.idle()

        except Exception as e:
            logger.error(f"Fehler beim Starten des Bots: {e}")
            raise

if __name__ == "__main__":
    try:
        logging.info("Starte Solana Trading Bot...")
        bot = SolanaWalletBot()
        bot.run()
    except Exception as e:
        logger.critical(f"Bot-Ausführung fehlgeschlagen: {e}")
        raise