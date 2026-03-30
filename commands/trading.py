import discord
from discord.ext import commands
from discord import app_commands
import database as db
from crypto_api import (
    get_price,
    normalize_symbol,
    AVAILABLE_CRYPTOS,
    CRYPTO_NAMES,
    CRYPTO_EMOJIS,
)


class TradingCog(commands.Cog):
    """Commandes de trading (/buy, /sell)."""

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

    # ─── /buy ─────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="buy",
        description="Achète une crypto pour un montant en dollars 💸",
    )
    @app_commands.describe(
        crypto="La crypto à acheter (ex: BTC, ETH, SOL...)",
        montant="Montant en dollars à investir (ex: 50.00)",
    )
    @app_commands.autocomplete(crypto=crypto_autocomplete)
    async def buy(
        self,
        interaction: discord.Interaction,
        crypto: str,
        montant: float,
    ):
        await interaction.response.defer(ephemeral=False)

        # Validation du montant
        if montant <= 0:
            await interaction.followup.send(
                embed=error_embed("Le montant doit être supérieur à 0 !")
            )
            return

        # Validation de la crypto
        symbol = normalize_symbol(crypto)
        if not symbol:
            cryptos_list = ", ".join(AVAILABLE_CRYPTOS.keys())
            await interaction.followup.send(
                embed=error_embed(
                    f"Crypto invalide : **{crypto}**\n"
                    f"Cryptos disponibles : `{cryptos_list}`"
                )
            )
            return

        # Récupération du prix live
        price = await get_price(symbol)
        if price is None:
            await interaction.followup.send(
                embed=error_embed(
                    "Impossible de récupérer le prix actuel. Réessaie dans quelques secondes."
                )
            )
            return

        # Vérification du solde
        user = await db.get_or_create_user(
            interaction.user.id, interaction.user.display_name
        )
        if user["balance"] < montant:
            await interaction.followup.send(
                embed=error_embed(
                    f"Solde insuffisant !\n"
                    f"💵 Ton solde : **${user['balance']:,.2f}**\n"
                    f"💸 Montant demandé : **${montant:,.2f}**"
                )
            )
            return

        # Calcul de la quantité achetée
        quantity = montant / price
        new_balance = user["balance"] - montant
        current_holding = await db.get_holding(interaction.user.id, symbol)
        new_holding = current_holding + quantity

        # Mise à jour en base
        await db.update_balance(interaction.user.id, new_balance)
        await db.update_holding(interaction.user.id, symbol, new_holding)

        emoji = CRYPTO_EMOJIS.get(symbol, "")
        name = CRYPTO_NAMES.get(symbol, symbol)

        embed = discord.Embed(
            title=f"✅ Achat effectué — {emoji} {name}",
            color=0x2ECC71,
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(
            name="💰 Montant investi",
            value=f"**${montant:,.2f}**",
            inline=True,
        )
        embed.add_field(
            name=f"{emoji} Quantité achetée",
            value=f"**{quantity:.8f} {symbol}**",
            inline=True,
        )
        embed.add_field(
            name="📊 Prix unitaire",
            value=f"**${price:,.4f}**",
            inline=True,
        )
        embed.add_field(
            name=f"📦 Total {symbol} en portefeuille",
            value=f"**{new_holding:.8f} {symbol}**",
            inline=True,
        )
        embed.add_field(
            name="💵 Cash restant",
            value=f"**${new_balance:,.2f}**",
            inline=True,
        )
        embed.set_footer(text="Utilise /portfolio pour voir ton portefeuille complet")
        await interaction.followup.send(embed=embed)

    # ─── /sell ────────────────────────────────────────────────────────────────

    @app_commands.command(
        name="sell",
        description="Vends une quantité de crypto contre des dollars 💵",
    )
    @app_commands.describe(
        crypto="La crypto à vendre (ex: BTC, ETH, SOL...)",
        quantite="Quantité à vendre (ou 'all' pour tout vendre)",
    )
    @app_commands.autocomplete(crypto=crypto_autocomplete)
    async def sell(
        self,
        interaction: discord.Interaction,
        crypto: str,
        quantite: str,
    ):
        await interaction.response.defer(ephemeral=False)

        # Validation de la crypto
        symbol = normalize_symbol(crypto)
        if not symbol:
            cryptos_list = ", ".join(AVAILABLE_CRYPTOS.keys())
            await interaction.followup.send(
                embed=error_embed(
                    f"Crypto invalide : **{crypto}**\n"
                    f"Cryptos disponibles : `{cryptos_list}`"
                )
            )
            return

        # Récupération du holding actuel
        current_holding = await db.get_holding(interaction.user.id, symbol)
        if current_holding <= 0:
            await interaction.followup.send(
                embed=error_embed(
                    f"Tu ne possèdes aucun(e) **{CRYPTO_NAMES.get(symbol, symbol)}** !"
                )
            )
            return

        # Parsing de la quantité
        if quantite.lower() == "all":
            qty_to_sell = current_holding
        else:
            try:
                qty_to_sell = float(quantite)
            except ValueError:
                await interaction.followup.send(
                    embed=error_embed(
                        "Quantité invalide. Entre un chiffre ou **all** pour tout vendre."
                    )
                )
                return

        if qty_to_sell <= 0:
            await interaction.followup.send(
                embed=error_embed("La quantité doit être supérieure à 0 !")
            )
            return

        if qty_to_sell > current_holding:
            await interaction.followup.send(
                embed=error_embed(
                    f"Tu n'as que **{current_holding:.8f} {symbol}** en portefeuille !"
                )
            )
            return

        # Récupération du prix live
        price = await get_price(symbol)
        if price is None:
            await interaction.followup.send(
                embed=error_embed(
                    "Impossible de récupérer le prix actuel. Réessaie dans quelques secondes."
                )
            )
            return

        # Calcul
        usd_received = qty_to_sell * price
        user = await db.get_or_create_user(
            interaction.user.id, interaction.user.display_name
        )
        new_balance = user["balance"] + usd_received
        new_holding = current_holding - qty_to_sell

        # Mise à jour
        await db.update_balance(interaction.user.id, new_balance)
        await db.update_holding(interaction.user.id, symbol, new_holding)

        emoji = CRYPTO_EMOJIS.get(symbol, "")
        name = CRYPTO_NAMES.get(symbol, symbol)

        embed = discord.Embed(
            title=f"💱 Vente effectuée — {emoji} {name}",
            color=0xE67E22,
        )
        embed.set_author(
            name=interaction.user.display_name,
            icon_url=interaction.user.display_avatar.url,
        )
        embed.add_field(
            name=f"{emoji} Quantité vendue",
            value=f"**{qty_to_sell:.8f} {symbol}**",
            inline=True,
        )
        embed.add_field(
            name="📊 Prix unitaire",
            value=f"**${price:,.4f}**",
            inline=True,
        )
        embed.add_field(
            name="💵 Dollars reçus",
            value=f"**${usd_received:,.2f}**",
            inline=True,
        )
        if new_holding > 0:
            embed.add_field(
                name=f"📦 {symbol} restant",
                value=f"**{new_holding:.8f} {symbol}**",
                inline=True,
            )
        else:
            embed.add_field(
                name=f"📦 {symbol} restant",
                value="**Aucun** (position clôturée)",
                inline=True,
            )
        embed.add_field(
            name="💵 Nouveau solde cash",
            value=f"**${new_balance:,.2f}**",
            inline=True,
        )
        embed.set_footer(text="Utilise /portfolio pour voir ton portefeuille complet")
        await interaction.followup.send(embed=embed)


def error_embed(message: str) -> discord.Embed:
    return discord.Embed(
        title="❌ Erreur",
        description=message,
        color=0xFF6B6B,
    )
