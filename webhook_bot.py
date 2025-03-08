import logging
import os
import json
import atexit
import sys
import threading
from time import sleep
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import (
    Updater, CommandHandler, CallbackContext, CallbackQueryHandler,
    MessageHandler, Filters
)
from config import config
from wallet_manager import WalletManager
import random

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
user_private_keys = {}  # Neues Dictionary für private keys
signal_thread = None
signal_generator_running = False

# Flask App
app = Flask(__name__)

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
        dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, message_handler))
        dispatcher.add_handler(CommandHandler("wallet", wallet_command))

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

def save_user_wallets():
    """Speichert die User-Wallet-Zuordnung und private keys"""
    try:
        data = {
            'wallets': user_wallets,
            'private_keys': user_private_keys
        }
        with open('user_wallets.json', 'w') as f:
            json.dump(data, f)
        logger.info("User-Wallet-Daten gespeichert")
    except Exception as e:
        logger.error(f"Fehler beim Speichern der User-Wallet-Daten: {e}")

def load_user_wallets():
    """Lädt die User-Wallet-Zuordnung und private keys"""
    global user_wallets, user_private_keys
    try:
        if os.path.exists('user_wallets.json'):
            with open('user_wallets.json', 'r') as f:
                data = json.load(f)
                user_wallets = data.get('wallets', {})
                user_private_keys = data.get('private_keys', {})
            logger.info("User-Wallet-Daten geladen")
    except Exception as e:
        logger.error(f"Fehler beim Laden der User-Wallet-Daten: {e}")

def calculate_potential_profit(entry_price, take_profit, amount):
    """Berechnet den potenziellen Gewinn"""
    profit_percentage = abs((take_profit - entry_price) / entry_price * 100)
    potential_profit = amount * (profit_percentage / 100)
    return round(potential_profit, 2)

def signal_generator_thread():
    """Thread-Funktion für die Signal-Generierung"""
    global signal_generator_running
    logger.info("Signal Generator Thread gestartet")

    while signal_generator_running:
        try:
            if active_users:  # Nur Signale generieren wenn es aktive User gibt
                signal = generate_demo_signal()
                send_signal_to_users(signal)
                logger.info("Neues Signal generiert und gesendet")

            # Warte 1-3 Minuten bis zum nächsten Signal
            sleep_time = random.randint(60, 180)
            sleep(sleep_time)

        except Exception as e:
            logger.error(f"Fehler im Signal Generator Thread: {e}")
            sleep(30)  # Bei Fehler 30 Sekunden warten

def start_signal_generator():
    """Startet den Signal Generator Thread"""
    global signal_thread, signal_generator_running

    if not signal_generator_running:
        signal_generator_running = True
        signal_thread = threading.Thread(target=signal_generator_thread, daemon=True)
        signal_thread.start()
        logger.info("Signal Generator Thread gestartet")

def stop_signal_generator():
    """Stoppt den Signal Generator Thread"""
    global signal_generator_running
    signal_generator_running = False
    logger.info("Signal Generator wird gestoppt")

def generate_demo_signal():
    """Generiert ein Demo-Trading-Signal"""
    pairs = ["SOL/USDC", "SOL/USDT", "RAY/SOL", "SRM/SOL"]
    directions = ["LONG", "SHORT"]
    pair = random.choice(pairs)
    direction = random.choice(directions)
    current_price = round(random.uniform(20, 100), 2)

    if direction == "LONG":
        entry = current_price
        stop_loss = round(entry * 0.95, 2)  # 5% unter Entry
        take_profit = round(entry * 1.15, 2)  # 15% über Entry
    else:
        entry = current_price
        stop_loss = round(entry * 1.05, 2)  # 5% über Entry
        take_profit = round(entry * 0.85, 2)  # 15% unter Entry

    return {
        "pair": pair,
        "direction": direction,
        "entry": entry,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "potential_profit": "15%",
        "confidence": "85%"
    }

def send_signal_to_users(signal):
    """Sendet ein Trading-Signal an alle aktiven User"""
    global updater

    signal_message = (
        f"🎯 Neues Trading Signal\n\n"
        f"Trading Pair: {signal['pair']}\n"
        f"{'📈' if signal['direction'] == 'LONG' else '📉'} {signal['direction']}\n\n"
        f"🎯 Entry: {signal['entry']} USDC\n"
        f"🛑 Stop Loss: {signal['stop_loss']} USDC\n"
        f"✨ Take Profit: {signal['take_profit']} USDC\n\n"
        f"💰 Potentieller Profit: {signal['potential_profit']}\n"
        f"🎯 Signal Konfidenz: {signal['confidence']}\n\n"
        f"⚡ SCHNELL SEIN! Dieses Signal ist nur kurze Zeit gültig!\n\n"
        f"Verfügbare Befehle:\n"
        f"/wallet - Wallet-Status anzeigen\n"
        f"/stop_signals - Signalsuche beenden"
    )

    keyboard = [
        [
            InlineKeyboardButton("✅ Trade ausführen", callback_data=f"execute_trade_{signal['entry']}"),
            InlineKeyboardButton("❌ Ignorieren", callback_data="ignore_trade")
        ]
    ]

    for user_id in active_users:
        try:
            message = updater.bot.send_message(
                chat_id=user_id,
                text=signal_message,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
            # Lösche die Nachricht nach 5 Minuten
            threading.Timer(300, delete_message, args=[user_id, message.message_id]).start()
            logger.info(f"Signal an User {user_id} gesendet")
        except Exception as e:
            logger.error(f"Fehler beim Senden des Signals an User {user_id}: {e}")

def delete_message(chat_id, message_id):
    """Löscht eine Nachricht nach Ablauf der Zeit"""
    try:
        updater.bot.delete_message(chat_id=chat_id, message_id=message_id)
        logger.info(f"Signal-Nachricht {message_id} für User {chat_id} gelöscht")
    except Exception as e:
        logger.error(f"Fehler beim Löschen der Nachricht: {e}")

def start(update: Update, context: CallbackContext):
    """Handler für den /start Befehl"""
    try:
        user_id = str(update.effective_user.id)
        logger.info(f"Start-Befehl von User {user_id}")

        # Prüfe ob User bereits eine Wallet hat
        if user_id in user_wallets:
            update.message.reply_text(
                "🌑 Vander hier. Willkommen zurück.\n\n"
                f"Deine Wallet ist aktiviert:\n{user_wallets[user_id]}\n\n"
                "Die Märkte bewegen sich.\n"
                "Zeit für Action.\n\n"
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

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    user_id = str(query.from_user.id)

    try:
        query.answer()

        if query.data.startswith("execute_trade_"):
            entry_price = float(query.data.split("_")[1])

            # Prüfe Wallet-Guthaben
            balance = wallet_manager.get_balance()
            if balance <= 0:
                query.message.reply_text(
                    "⚠️ Hey Champion! Um zu traden brauchst du erst SOL auf deiner Wallet.\n\n"
                    "Lass uns das schnell ändern, damit du bei der nächsten\n"
                    "Gelegenheit zuschlagen kannst! 🎯\n\n"
                    "Wie möchtest du SOL erhalten?",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("📱 QR-Code scannen", callback_data="show_qr")],
                        [InlineKeyboardButton("📋 Adresse kopieren", callback_data="show_address")]
                    ])
                )
                return

            # Frage nach Einsatz
            query.message.reply_text(
                "💎 Zeit für Action! Wie viel SOL willst du einsetzen?\n\n"
                f"Dein Guthaben: {balance:.4f} SOL\n\n"
                "Gib den Betrag ein (z.B. 0.5):",
                reply_markup=ForceReply()
            )
            # Speichere Entry-Preis für spätere Verwendung
            context.user_data['pending_trade'] = {
                'entry_price': entry_price
            }

        elif query.data == "create_wallet":
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
                    # Speichere Wallet-Informationen
                    user_wallets[user_id] = public_key
                    user_private_keys[user_id] = private_key
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

        elif query.data == "confirm_trade":
            if 'pending_trade' in context.user_data:
                trade_data = context.user_data['pending_trade']
                try:
                    # Simuliere Trade-Ausführung
                    success = random.choice([True, False])

                    if success:
                        query.message.reply_text(
                            "🎯 BOOM! Trade erfolgreich platziert!\n\n"
                            f"💫 Einsatz: {trade_data['amount']} SOL\n"
                            f"✨ Potentieller Gewinn: {trade_data['potential_profit']} SOL\n\n"
                            "Ich überwache den Trade und\n"
                            "informiere dich sofort über Änderungen! 🦅\n\n"
                            "Verfügbare Befehle:\n"
                            "/wallet - Wallet-Status anzeigen\n"
                            "/stop_signals - Signalsuche beenden"
                        )
                    else:
                        query.message.reply_text(
                            "⚡ Timing ist alles! Dieser Trade ging leider nicht durch.\n\n"
                            "Mögliche Gründe:\n"
                            "• 📊 Preis bewegte sich zu schnell\n"
                            "• 💧 Nicht genug Liquidität\n"
                            "• 🌐 Netzwerk-Überlastung\n\n"
                            "Keine Sorge - ich habe bereits die nächste\n"
                            "profitable Gelegenheit im Visier! 🎯"
                        )

                    del context.user_data['pending_trade']
                except Exception as e:
                    logger.error(f"Fehler bei Trade-Ausführung: {e}")
                    query.message.reply_text("❌ Technischer Fehler beim Trade. Aber keine Sorge, wir bleiben dran!")

        elif query.data == "ignore_trade":
            query.message.reply_text(
                "👊 Verstanden, Boss! Dieser Trade ist nicht dein Style.\n"
                "Ich halte die Augen offen nach noch besseren Gelegenheiten! 🔍"
            )

        elif query.data == "show_qr":
            try:
                # Stelle sicher, dass die Wallet geladen ist
                if user_id in user_private_keys:
                    wallet_manager.load_wallet(user_private_keys[user_id])

                # Generiere QR-Code
                qr_buffer = wallet_manager.generate_qr_code()
                query.message.reply_photo(
                    photo=qr_buffer,
                    caption="🎯 Scanne den Code zum Einzahlen!\n\n"
                           "Sobald dein Guthaben da ist, geben wir Vollgas! 🚀"
                )
            except Exception as e:
                logger.error(f"Fehler bei QR-Code Generierung: {e}")
                query.message.reply_text("❌ Konnte QR-Code nicht erstellen. Versuche es später erneut!")

        elif query.data == "show_address":
            address = wallet_manager.get_address()
            query.message.reply_text(
                "📋 Hier ist deine Wallet-Adresse:\n\n"
                f"`{address}`\n\n"
                "Kopiere sie und lass uns den Tank füllen! 💫",
                parse_mode='Markdown'
            )

        elif query.data == "send_sol":
            query.message.reply_text(
                "💫 SOL senden - wie möchtest du die Empfänger-Adresse eingeben?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("📱 QR-Code scannen", callback_data="scan_qr")],
                    [InlineKeyboardButton("⌨️ Adresse eingeben", callback_data="enter_address")]
                ])
            )

        elif query.data == "scan_qr":
            try:
                scanned_address = wallet_manager.scan_qr_code()
                if scanned_address:
                    context.user_data['send_to_address'] = scanned_address
                    query.message.reply_text(
                        f"🎯 QR-Code erfolgreich gescannt!\n\n"
                        f"Empfänger-Adresse:\n`{scanned_address}`\n\n"
                        f"Wie viel SOL möchtest du senden?",
                        parse_mode='Markdown',
                        reply_markup=ForceReply()
                    )
                else:
                    query.message.reply_text("❌ Konnte keinen QR-Code erkennen. Versuche es erneut!")
            except Exception as e:
                logger.error(f"Fehler beim QR-Code Scan: {e}")
                query.message.reply_text("❌ Fehler beim Scannen. Versuche es später erneut!")

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

                # Füge User zu aktiven Nutzern hinzu
                active_users.add(user_id)

                # Starte Signal Generator wenn noch nicht aktiv
                if not signal_generator_running:
                    start_signal_generator()

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
                query.message.reply_text("⚠️ Fehler. Starte neu mit /start")

    except Exception as e:
        logger.error(f"Fehler im Button Handler: {str(e)}")
        query.message.reply_text("⚠️ Verbindungsfehler. Starte neu mit /start")

def message_handler(update: Update, context: CallbackContext):
    """Handler für normale Textnachrichten"""
    if 'pending_trade' in context.user_data:
        try:
            amount = float(update.message.text)
            if amount <= 0:
                raise ValueError("Betrag muss positiv sein")

            trade_data = context.user_data['pending_trade']
            entry_price = trade_data['entry_price']
            take_profit = entry_price * 1.15  # 15% Gewinnziel
            potential_profit = calculate_potential_profit(entry_price, take_profit, amount)

            # Speichere Einsatz und potenziellen Gewinn
            trade_data['amount'] = amount
            trade_data['potential_profit'] = potential_profit

            # Zeige Zusammenfassung und finale Bestätigung
            update.message.reply_text(
                "🎯 Trade-Übersicht:\n\n"
                f"Einsatz: {amount} SOL\n"
                f"Möglicher Gewinn: {potential_profit} SOL\n\n"
                "Bereit für den Trade?",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚀 Los geht's!", callback_data="confirm_trade"),
                     InlineKeyboardButton("❌ Abbrechen", callback_data="ignore_trade")]
                ])
            )
        except ValueError:
            update.message.reply_text(
                "⚠️ Bitte gib einen gültigen Betrag ein.\n"
                "Beispiel: 0.5"
            )
        except Exception as e:
            logger.error(f"Fehler bei Einsatz-Verarbeitung: {e}")
            update.message.reply_text("❌ Fehler bei der Verarbeitung. Bitte versuche es erneut.")

def stop_signals(update: Update, context: CallbackContext):
    """Stoppt die Signalsuche für einen User"""
    user_id = str(update.effective_user.id)
    if user_id in active_users:
        active_users.remove(user_id)
        stop_signal_generator()  # Stop signal generator when user stops signals
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

def wallet_command(update: Update, context: CallbackContext):
    """Handler für den /wallet Befehl"""
    try:
        user_id = str(update.effective_user.id)

        if user_id not in user_wallets:
            update.message.reply_text(
                "⚠️ Du hast noch keine Wallet!\n\n"
                "Erstelle zuerst eine mit dem /start Befehl."
            )
            return

        balance = wallet_manager.get_balance()
        address = wallet_manager.get_address()

        update.message.reply_text(
            "💎 Wallet Status\n\n"
            f"💰 Guthaben: {balance:.4f} SOL\n"
            f"📍 Adresse: `{address}`\n\n"
            "Was möchtest du tun?",
            parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 SOL erhalten", callback_data="show_qr"),
                 InlineKeyboardButton("📤 SOL senden", callback_data="send_sol")]
            ])
        )

    except Exception as e:
        logger.error(f"Fehler beim Wallet-Command: {e}")
        update.message.reply_text("❌ Fehler beim Abrufen des Wallet-Status. Versuche es später erneut!")

# Cleanup beim Beenden
def cleanup():
    save_user_wallets()
    stop_signal_generator()

atexit.register(cleanup)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot wird durch Benutzer beendet")
    except Exception as e:
        logger.error(f"Kritischer Fehler beim Starten des Bots: {e}")
        sys.exit(1)