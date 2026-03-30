import io
import discord
from discord.ext import commands
from discord import app_commands
import pandas as pd
import mplfinance as mpf
import asyncio

from crypto_api import get_ohlc, normalize_symbol, AVAILABLE_CRYPTOS, CRYPTO_NAMES, CRYPTO_EMOJIS


class ChartCog(commands.Cog):
    """Commande /chart — affiche un graphique en chandelier."""

    # ─── Autocomplete crypto ─────────────────────────────────────────────────

    async def crypto_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        choices = []
        for sym, name in CRYPTO_NAMES.items():
            emoji = CRYPTO_EMOJIS.get(sym, "")
            label = f"{emoji} {name} ({sym})"
            if current.upper() in sym or current.lower() in name.lower():
                choices.append(app_commands.Choice(name=label, value=sym))
        return choices[:10]

    # ─── /chart ──────────────────────────────────────────────────────────────

    @app_commands.command(
        name="chart",
        description="Affiche le graphique des prix en chandelier pour une crypto 📈",
    )
    @app_commands.describe(
        crypto="La crypto à analyser (ex: BTC, ETH...)",
        periode="La période de temps à afficher",
    )
    @app_commands.choices(
        periode=[
            app_commands.Choice(name="1 Jour", value="1"),
            app_commands.Choice(name="7 Jours", value="7"),
            app_commands.Choice(name="14 Jours", value="14"),
            app_commands.Choice(name="30 Jours", value="30"),
            app_commands.Choice(name="90 Jours", value="90"),
            app_commands.Choice(name="1 An", value="365"),
        ]
    )
    @app_commands.autocomplete(crypto=crypto_autocomplete)
    async def chart(
        self,
        interaction: discord.Interaction,
        crypto: str,
        periode: app_commands.Choice[str],
    ):
        await interaction.response.defer(ephemeral=False)

        symbol = normalize_symbol(crypto)
        if not symbol:
            cryptos_list = ", ".join(AVAILABLE_CRYPTOS.keys())
            embed = discord.Embed(
                title="❌ Erreur",
                description=f"Crypto invalide : **{crypto}**\nCryptos disponibles : `{cryptos_list}`",
                color=0xFF6B6B,
            )
            await interaction.followup.send(embed=embed)
            return

        # Récupération des données OHLC
        data = await get_ohlc(symbol, periode.value)
        if not data:
            embed = discord.Embed(
                title="❌ Erreur API",
                description="Impossible de récupérer l'historique de prix. L'API locale est peut-être bloquée temporairement, réessaye dans quelques minutes !",
                color=0xFF6B6B,
            )
            await interaction.followup.send(embed=embed)
            return

        # La génération de l'image peut prendre quelques centièmes de seconde 
        # (bloquant potentiellement l'event loop), donc on l'envoie dans un thread.
        try:
            file = await asyncio.to_thread(self.generate_chart, symbol, periode.name, data)
        except Exception as e:
            embed = discord.Embed(
                title="❌ Erreur Graphique",
                description=f"Erreur technique lors de la génération du graphique: {e}",
                color=0xFF6B6B,
            )
            await interaction.followup.send(embed=embed)
            return

        name = CRYPTO_NAMES.get(symbol, symbol)
        emoji = CRYPTO_EMOJIS.get(symbol, "")

        embed = discord.Embed(
            title=f"📈 Chart — {emoji} {name} ({symbol})",
            description=f"Période: **{periode.name}**",
            color=0x2C3E50,
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.set_image(url="attachment://chart.png")
        embed.set_footer(text="Généré par mplfinance • API: CoinGecko")

        await interaction.followup.send(embed=embed, file=file)

    def generate_chart(self, symbol: str, periode_name: str, data: list[list[float]]) -> discord.File:
        """Génère l'image PNG en chandelier avec pandas et mplfinance."""
        # Les données CoinGecko sont au format : [timestamp, open, high, low, close]
        df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close"])
        df["Datetime"] = pd.to_datetime(df["timestamp"], unit='ms')
        df.set_index("Datetime", inplace=True)

        # Si l'API retourne une liste vide
        if df.empty:
            raise ValueError("Aucune donnée retournée par l'API")

        # Configuration des couleurs : Bougies vertes si ++, rouges si --
        mc = mpf.make_marketcolors(
            up='#2ecc71',      # Vert clair pour les hausses
            down='#e74c3c',    # Rouge clair pour les baisses
            edge='inherit',    # Bords de la même couleur
            wick='inherit',    # Mèches de la même couleur
            volume='in', 
            ohlc='inherit'
        )
        
        # Style global (fond sombre)
        s = mpf.make_mpf_style(
            base_mpf_style='nightclouds', # Style prédéfini sombre
            marketcolors=mc,
            gridstyle='dashed',           # Grille pointillée
            gridcolor='#3a3a3a'           # Grille grise très sombre
        )

        buf = io.BytesIO()
        mpf.plot(
            df, 
            type='candle',  # Type chandelier
            style=s, 
            title=f"{symbol} / USD - {periode_name}", 
            ylabel="Prix ($)",
            savefig=dict(fname=buf, format='png', bbox_inches='tight', dpi=100),
            tight_layout=True,
            warn_too_much_data=2000 # Évite un warning inutile si beaucoup de bougies
        )
        
        buf.seek(0)
        return discord.File(fp=buf, filename="chart.png")
