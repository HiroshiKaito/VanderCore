import discord
import logging
from typing import Optional
import os
from datetime import datetime

logger = logging.getLogger(__name__)

class TradingBotDiscord:
    def __init__(self):
        self.client = discord.Client(intents=discord.Intents.default())
        self.trading_channel: Optional[discord.TextChannel] = None
        
        @self.client.event
        async def on_ready():
            logger.info(f'Discord Bot eingeloggt als {self.client.user}')
            # Suche nach dem Trading-Channel
            for guild in self.client.guilds:
                channel = discord.utils.get(guild.text_channels, name='trading-signals')
                if channel:
                    self.trading_channel = channel
                    logger.info(f'Trading Channel gefunden: {channel.name}')
                    break
    
    async def send_trading_signal(self, signal_data: dict):
        """Sendet ein Trading Signal an den Discord Channel"""
        if not self.trading_channel:
            logger.error("Kein Trading Channel gefunden")
            return

        try:
            # Erstelle ein schönes Embed für das Signal
            embed = discord.Embed(
                title="🚨 Neues Trading Signal!",
                description="Solana Trading Opportunity",
                color=discord.Color.blue() if signal_data.get('direction') == 'long' else discord.Color.red(),
                timestamp=datetime.now()
            )

            # Füge Signal Details hinzu
            embed.add_field(
                name="Signal Typ",
                value=f"{'📈 LONG' if signal_data.get('direction') == 'long' else '📉 SHORT'}",
                inline=False
            )
            embed.add_field(
                name="Einstiegspreis",
                value=f"${signal_data.get('entry', 0):.2f}",
                inline=True
            )
            embed.add_field(
                name="Take Profit",
                value=f"${signal_data.get('take_profit', 0):.2f}",
                inline=True
            )
            embed.add_field(
                name="Stop Loss",
                value=f"${signal_data.get('stop_loss', 0):.2f}",
                inline=True
            )

            # Füge Zusatzinformationen hinzu
            if 'signal_quality' in signal_data:
                embed.add_field(
                    name="Signal Qualität",
                    value=f"{signal_data['signal_quality']}/10 ⭐",
                    inline=True
                )
            if 'expected_profit' in signal_data:
                embed.add_field(
                    name="Erwarteter Profit",
                    value=f"{signal_data['expected_profit']:.1f}% 💰",
                    inline=True
                )

            # Sende das Embed
            await self.trading_channel.send(embed=embed)
            logger.info("Trading Signal erfolgreich an Discord gesendet")

        except Exception as e:
            logger.error(f"Fehler beim Senden des Discord Signals: {e}")

    def start(self):
        """Startet den Discord Bot"""
        try:
            token = os.getenv('DISCORD_BOT_TOKEN')
            if not token:
                logger.error("Kein Discord Bot Token gefunden")
                return
            self.client.run(token)
        except Exception as e:
            logger.error(f"Fehler beim Starten des Discord Bots: {e}")

    def stop(self):
        """Stoppt den Discord Bot"""
        try:
            if self.client:
                self.client.close()
                logger.info("Discord Bot gestoppt")
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Discord Bots: {e}")
