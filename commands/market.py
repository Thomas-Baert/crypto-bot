import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
from crypto_api import get_prices, AVAILABLE_CRYPTOS, CRYPTO_NAMES, CRYPTO_EMOJIS


class MarketCog(commands.Cog):
    """Commande /market — affiche les prix live de toutes les cryptos."""

    @app_commands.command(
        name="market",
        description="Affiche les prix actuels de toutes les cryptos disponibles 💹",
    )
    async def market(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        all_symbols = list(AVAILABLE_CRYPTOS.keys())
        prices = await get_prices(all_symbols)

        lines = []
        for sym in all_symbols:
            emoji = CRYPTO_EMOJIS.get(sym, "•")
            name = CRYPTO_NAMES.get(sym, sym)
            price = prices.get(sym)

            if price is None:
                price_str = "*indisponible*"
            elif price >= 1000:
                price_str = f"**${price:,.2f}**"
            elif price >= 1:
                price_str = f"**${price:,.4f}**"
            else:
                price_str = f"**${price:.6f}**"

            lines.append(f"{emoji} **{name}** `{sym}` — {price_str}")

        now = datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")

        embed = discord.Embed(
            title="💹 Marché — Prix en temps réel",
            description="\n".join(lines),
            color=0x1ABC9C,
        )
        embed.set_footer(text=f"Mis à jour le {now} • Source : CoinGecko")

        await interaction.followup.send(embed=embed)
