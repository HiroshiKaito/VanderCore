"""
Bot-Hauptdatei für Solana Trading Bot
"""
import logging
import os
from webhook_bot import main

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logging.error(f"Fehler beim Starten des Bots: {e}")
        raise