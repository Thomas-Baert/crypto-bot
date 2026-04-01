import discord
from discord.ext import commands
from discord import app_commands
import database as db
from crypto_api import get_prices, get_dexscreener_tokens, CRYPTO_NAMES, CRYPTO_EMOJIS


class PortfolioCog(commands.Cog):
    """Commande /portfolio — affiche le portefeuille complet."""

    @app_commands.command(
        name="portfolio",
        description="Affiche ton portefeuille complet avec les prix actuels 📊",
    )
    async def portfolio(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        user = await db.get_or_create_user(
            interaction.user.id, interaction.user.display_name
        )
        holdings = await db.get_holdings(interaction.user.id)

        embed = discord.Embed(
            title="📊 Portefeuille",
            color=0x3498DB,
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )

        portfolio_value = 0.0

        if not holdings:
            embed.description = (
                "Tu ne possèdes aucune crypto pour l'instant.\n"
                "Utilise `/buy` pour commencer à investir !"
            )
        else:
            cg_symbols = [h["crypto_id"] for h in holdings if not h["crypto_id"].startswith("meme:")]
            meme_symbols = [h["crypto_id"] for h in holdings if h["crypto_id"].startswith("meme:")]

            prices = await get_prices(cg_symbols) if cg_symbols else {}
            meme_data = await get_dexscreener_tokens(meme_symbols) if meme_symbols else {}
            
            # On fusionne les prix dans un seul dict pour simplifier la boucle
            for k, v in meme_data.items():
                prices[k] = v["price"]

            lines = []
            for h in sorted(holdings, key=lambda x: x["crypto_id"]):
                sym = h["crypto_id"]
                amount = h["amount"]
                price = prices.get(sym) or 0.0
                value = amount * price

                portfolio_value += value

                if sym.startswith("meme:"):
                    emoji = "🪙"
                    # On utilise le nom et le symbole réels si disponibles
                    token_info = meme_data.get(sym, {})
                    real_name = token_info.get("name", "Memecoin")
                    real_symbol = token_info.get("symbol", sym.replace("meme:", "")[:8] + "...")
                    
                    name = f"{real_name}"
                    display_sym = real_symbol
                else:
                    emoji = CRYPTO_EMOJIS.get(sym, "•")
                    display_sym = sym
                    name = CRYPTO_NAMES.get(sym, sym)

                if price > 0:
                    lines.append(
                        f"{emoji} **{name}** ({display_sym})\n"
                        f"┣ Quantité : `{amount:,.6f}`\n"
                        f"┣ Prix unitaire : `${price:,.10f}`\n"
                        f"┗ Valeur : **${value:,.2f}**"
                    )
                else:
                    lines.append(
                        f"{emoji} **{name}** ({display_sym})\n"
                        f"┣ Quantité : `{amount:,.6f}`\n"
                        f"┗ Prix : *indisponible*"
                    )

            embed.description = "\n\n".join(lines)

        total = user["balance"] + portfolio_value

        embed.add_field(
            name="💵 Cash disponible",
            value=f"**${user['balance']:,.2f}**",
            inline=True,
        )
        embed.add_field(
            name="📈 Valeur crypto",
            value=f"**${portfolio_value:,.2f}**",
            inline=True,
        )
        embed.add_field(
            name="🏆 Total",
            value=f"**${total:,.2f}**",
            inline=True,
        )
        embed.set_footer(text="Prix en temps réel via CoinGecko")

        await interaction.followup.send(embed=embed)
