import asyncio
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv

import database as db
from crypto_api import close_session
from commands.economy import EconomyCog
from commands.trading import TradingCog
from commands.portfolio import PortfolioCog
from commands.market import MarketCog
from commands.leaderboard import LeaderboardCog
from commands.chart import ChartCog

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")


class CryptoBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Initialise la base de données
        await db.init_db()

        # Enregistre les Cogs
        await self.add_cog(EconomyCog())
        await self.add_cog(TradingCog())
        await self.add_cog(PortfolioCog())
        await self.add_cog(MarketCog())
        await self.add_cog(LeaderboardCog())
        await self.add_cog(ChartCog())

        # Sync les commandes
        if GUILD_ID:
            # Sync vers un seul serveur (instantané, utile en dev)
            guild = discord.Object(id=int(GUILD_ID))
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            print(f"[✓] Slash commands synced to guild {GUILD_ID}")
        else:
            # Sync globale (peut prendre jusqu'à 1h sur Discord)
            await self.tree.sync()
            print("[✓] Slash commands synced globally")

    async def on_ready(self):
        print(f"[✓] Connecté en tant que {self.user} (ID: {self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="📈 le marché crypto",
            )
        )

    async def close(self):
        await close_session()
        await super().close()


async def main():
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN manquant dans le fichier .env !")

    bot = CryptoBot()
    async with bot:
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
