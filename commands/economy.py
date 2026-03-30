import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone, timedelta
import database as db


class EconomyCog(commands.Cog):
    """Commandes liées à l'économie virtuelle (/daily, /balance)."""

    # ─── /daily ───────────────────────────────────────────────────────────────

    @app_commands.command(name="daily", description="Réclame tes 100$ quotidiens 💵")
    async def daily(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        user = await db.get_or_create_user(
            interaction.user.id, interaction.user.display_name
        )
        now = datetime.now(timezone.utc)

        # Vérification du cooldown (24h)
        if user["last_daily"]:
            last = datetime.fromisoformat(user["last_daily"])
            delta = now - last
            if delta < timedelta(hours=24):
                remaining = timedelta(hours=24) - delta
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)

                embed = discord.Embed(
                    title="⏳ Daily déjà réclamé !",
                    description=(
                        f"Tu as déjà réclamé ton daily aujourd'hui.\n"
                        f"Reviens dans **{hours}h {minutes}min** !"
                    ),
                    color=0xFF6B6B,
                )
                embed.set_footer(text=f"Solde actuel : ${user['balance']:,.2f}")
                await interaction.followup.send(embed=embed)
                return

        new_balance = user["balance"] + 100.0
        await db.update_balance(interaction.user.id, new_balance)
        await db.update_last_daily(interaction.user.id, now.isoformat())

        embed = discord.Embed(
            title="💰 Daily réclamé !",
            description=f"**+100$** ont été ajoutés à ton solde !",
            color=0x2ECC71,
        )
        embed.add_field(name="💵 Nouveau solde (cash)", value=f"**${new_balance:,.2f}**", inline=False)
        embed.set_footer(text=f"Reviens demain pour un nouveau daily !")
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        await interaction.followup.send(embed=embed)

    # ─── /balance ─────────────────────────────────────────────────────────────

    @app_commands.command(name="balance", description="Consulte ton solde total 💼")
    async def balance(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        from crypto_api import get_prices, CRYPTO_NAMES, CRYPTO_EMOJIS

        user = await db.get_or_create_user(
            interaction.user.id, interaction.user.display_name
        )
        holdings = await db.get_holdings(interaction.user.id)

        # Calcul de la valeur du portfolio
        portfolio_value = 0.0
        if holdings:
            symbols = [h["crypto_id"] for h in holdings]
            prices = await get_prices(symbols)
            for h in holdings:
                price = prices.get(h["crypto_id"]) or 0.0
                portfolio_value += h["amount"] * price

        total = user["balance"] + portfolio_value

        embed = discord.Embed(
            title="💼 Ton portefeuille",
            color=0x3498DB,
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(
            name="💵 Cash disponible",
            value=f"**${user['balance']:,.2f}**",
            inline=True,
        )
        embed.add_field(
            name="📈 Valeur du portfolio",
            value=f"**${portfolio_value:,.2f}**",
            inline=True,
        )
        embed.add_field(
            name="🏆 Total",
            value=f"**${total:,.2f}**",
            inline=False,
        )

        if user["last_daily"]:
            last = datetime.fromisoformat(user["last_daily"])
            next_daily = last + timedelta(hours=24)
            now = datetime.now(timezone.utc)
            if now < next_daily:
                remaining = next_daily - now
                hours = int(remaining.total_seconds() // 3600)
                minutes = int((remaining.total_seconds() % 3600) // 60)
                embed.set_footer(text=f"⏳ Prochain daily dans {hours}h {minutes}min")
            else:
                embed.set_footer(text="✅ Tu peux réclamer ton daily avec /daily !")
        else:
            embed.set_footer(text="✅ Tu peux réclamer ton daily avec /daily !")

        await interaction.followup.send(embed=embed)
