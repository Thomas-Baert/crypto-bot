import io
import discord
from discord.ext import commands
from discord import app_commands
import database as db
import asyncio
import pandas as pd
import mplfinance as mpf
from crypto_api import get_dexscreener_token, get_geckoterminal_ohlc


class MemeCog(commands.Cog):
    """Commandes liées à l'achat et la visualisation de memecoins via CA."""

    def __init__(self, bot):
        self.bot = bot

    meme_group = app_commands.Group(name="meme", description="Spéculation sur les memecoins via leur Contrat")

    # ─── /meme infos ────────────────────────────────────────────────────────

    @meme_group.command(name="infos", description="Affiche les infos d'un jeton DexScreener")
    @app_commands.describe(contrat="L'adresse du contrat (ex: 7bgL...)")
    async def meme_infos(self, interaction: discord.Interaction, contrat: str):
        await interaction.response.defer(ephemeral=False)
        
        token_data = await get_dexscreener_token(contrat)
        if not token_data:
            await interaction.followup.send(embed=error_embed("Jeton introuvable ou erreur de l'API DexScreener."))
            return

        embed = discord.Embed(
            title=f"🪙 {token_data['name']} ({token_data['symbol']})",
            description=f"**Réseau :** `{token_data['network'].upper()}`\n**Contrat :** `{contrat}`",
            color=0x1ABC9C
        )
        embed.add_field(name="Prix Unitaire", value=f"${token_data['price']:,.8f}", inline=True)
        embed.add_field(name="Liquidité (Pool)", value=f"${token_data['liquidity']:,.0f}", inline=True)
        
        if token_data['liquidity'] < 5000:
            embed.set_footer(text="⚠️ Attention : Ce jeton a très peu de liquidité. Achat bloqué.")
        else:
            embed.set_footer(text="✅ Statut : Achat autorisé")

        await interaction.followup.send(embed=embed)


    # ─── /meme buy ────────────────────────────────────────────────────────

    @meme_group.command(name="buy", description="Achète un memecoin via son contrat")
    @app_commands.describe(contrat="L'adresse du contrat (Solana, Base, etc.)", montant_usd="Le montant en $ à acheter")
    async def meme_buy(self, interaction: discord.Interaction, contrat: str, montant_usd: float):
        if montant_usd <= 0:
            await interaction.response.send_message(embed=error_embed("Le montant doit être positif."), ephemeral=True)
            return

        await interaction.response.defer(ephemeral=False)

        # Vérification du solde utilisateur
        user = await db.get_or_create_user(interaction.user.id, interaction.user.display_name)
        if user["balance"] < montant_usd:
            await interaction.followup.send(embed=error_embed(f"Solde insuffisant ! Tu as **${user['balance']:,.2f}**."))
            return

        # Fetch token
        token_data = await get_dexscreener_token(contrat)
        if not token_data:
            await interaction.followup.send(embed=error_embed("Jeton introuvable. As-tu mis le bon contrat ?"))
            return

        if token_data['price'] == 0:
            await interaction.followup.send(embed=error_embed("Impossible de récupérer le prix. Il vaut 0 ?"))
            return

        if token_data['liquidity'] < 5000:
             await interaction.followup.send(embed=error_embed(f"Liquidité insuffisante (${token_data['liquidity']:,.0f}). Le seuil minimum est de $5000 pour éviter les scams."))
             return

        quantite = montant_usd / token_data['price']
        crypto_id = f"meme:{contrat}"

        new_balance = user["balance"] - montant_usd
        await db.update_balance(interaction.user.id, new_balance)

        current_qty = await db.get_holding(interaction.user.id, crypto_id)
        await db.update_holding(interaction.user.id, crypto_id, current_qty + quantite)

        embed = discord.Embed(
            title="✅ Achat Memecoin Réussi",
            description=f"Tu as acheté **{quantite:,.2f} {token_data['symbol']}** !",
            color=0x2ECC71
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Coût Total", value=f"${montant_usd:,.2f}", inline=True)
        embed.add_field(name="Prix d'achat", value=f"${token_data['price']:,.8f}", inline=True)
        embed.add_field(name="Nouveau Solde Cash", value=f"${new_balance:,.2f}", inline=False)
        embed.set_footer(text=f"Nom du jeton : {token_data['name']}")

        await interaction.followup.send(embed=embed)


    # ─── /meme sell ───────────────────────────────────────────────────────

    @meme_group.command(name="sell", description="Vend tes memecoins")
    @app_commands.describe(contrat="L'adresse du contrat à vendre", quantite="La quantité à vendre (tape 'all' pour tout vendre)")
    async def meme_sell(self, interaction: discord.Interaction, contrat: str, quantite: str):
        await interaction.response.defer(ephemeral=False)
        
        crypto_id = f"meme:{contrat}"
        current_qty = await db.get_holding(interaction.user.id, crypto_id)

        if current_qty <= 0:
            await interaction.followup.send(embed=error_embed("Tu ne possèdes pas de jetons sur ce contrat !"))
            return

        if quantite.lower() == "all":
            qty_to_sell = current_qty
        else:
            try:
                qty_to_sell = float(quantite)
            except ValueError:
                await interaction.followup.send(embed=error_embed("La quantité doit être un nombre ou 'all'."))
                return

            if qty_to_sell <= 0:
                await interaction.followup.send(embed=error_embed("La quantité doit être positive."))
                return

            if qty_to_sell > current_qty:
                await interaction.followup.send(embed=error_embed(f"Tu n'en possèdes pas assez ! Tu as **{current_qty:,.4f}**."))
                return

        token_data = await get_dexscreener_token(contrat)
        if not token_data or token_data['price'] == 0:
            await interaction.followup.send(embed=error_embed("Impossible de récupérer le prix actuel pour la revente."))
            return

        total_value = qty_to_sell * token_data['price']

        # Update DB
        user = await db.get_user(interaction.user.id)
        new_balance = user["balance"] + total_value
        await db.update_balance(interaction.user.id, new_balance)

        new_qty = current_qty - qty_to_sell
        if new_qty < 1e-8:
            new_qty = 0.0
        await db.update_holding(interaction.user.id, crypto_id, new_qty)

        embed = discord.Embed(
            title="🤝 Vente Memecoin Réussie",
            description=f"Tu as vendu **{qty_to_sell:,.2f} {token_data['symbol']}** !",
            color=0x3498DB
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="Gains", value=f"+${total_value:,.2f}", inline=True)
        embed.add_field(name="Prix de vente", value=f"${token_data['price']:,.8f}", inline=True)
        embed.add_field(name="Nouveau Solde Cash", value=f"${new_balance:,.2f}", inline=False)

        await interaction.followup.send(embed=embed)


    # ─── /meme chart ────────────────────────────────────────────────────────
    
    @meme_group.command(name="chart", description="Dessine le graphique en chandelier d'un memecoin")
    @app_commands.describe(contrat="L'adresse du contrat", periode="1 Jour, 1 Heure ou 1 Minute")
    @app_commands.choices(
        periode=[
            app_commands.Choice(name="Graphique Journalier", value="day"),
            app_commands.Choice(name="Graphique Horaire", value="hour"),
            app_commands.Choice(name="Graphique Minute", value="minute"),
        ]
    )
    async def meme_chart(self, interaction: discord.Interaction, contrat: str, periode: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=False)
        
        token_data = await get_dexscreener_token(contrat)
        if not token_data or not token_data["pool_address"]:
            await interaction.followup.send(embed=error_embed("Jeton introuvable ou pool de liquidité non détecté."))
            return

        net = token_data["network"]
        pool = token_data["pool_address"]
        symbol = token_data["symbol"]

        data = await get_geckoterminal_ohlc(net, pool, periode.value)
        if not data:
            await interaction.followup.send(embed=error_embed("Impossible de récupérer l'historique de prix depuis GeckoTerminal API."))
            return

        try:
            file = await asyncio.to_thread(self._generate_chart, symbol, periode.name, data)
            embed = discord.Embed(
                title=f"📈 Chart — {token_data['name']} ({symbol})",
                description=f"**Réseau:** `{net}` | **Contrat:** `{contrat}`\n**Période:** {periode.name} (200 bougies)",
                color=0x2C3E50,
            )
            embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
            embed.set_image(url="attachment://meme_chart.png")
            embed.set_footer(text="Généré par mplfinance • API: GeckoTerminal")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
             await interaction.followup.send(embed=error_embed(f"Erreur technique lors de la génération du graphique: {e}"))

    def _generate_chart(self, symbol: str, periode_name: str, data: list[list[float]]) -> discord.File:
        """Génère l'image PNG en chandelier avec pandas et mplfinance."""
        # Les données GeckoTerminal sont au format : [timestamp, open, high, low, close]
        df = pd.DataFrame(data, columns=["timestamp", "Open", "High", "Low", "Close"])
        df["Datetime"] = pd.to_datetime(df["timestamp"], unit='s') # GeckoTerminal est en secondes
        df.set_index("Datetime", inplace=True)

        if df.empty:
            raise ValueError("Aucune donnée retournée par l'API OHLC")

        mc = mpf.make_marketcolors(
            up='#2ecc71',      
            down='#e74c3c',    
            edge='inherit',    
            wick='inherit',    
            volume='in', 
            ohlc='inherit'
        )
        
        s = mpf.make_mpf_style(
            base_mpf_style='nightclouds', 
            marketcolors=mc,
            gridstyle='dashed',           
            gridcolor='#3a3a3a'           
        )

        buf = io.BytesIO()
        mpf.plot(
            df, 
            type='candle',  
            style=s, 
            title=f"{symbol} / USD - {periode_name}", 
            ylabel="Prix ($)",
            savefig=dict(fname=buf, format='png', bbox_inches='tight', dpi=100),
            tight_layout=True,
            warn_too_much_data=2000
        )
        
        buf.seek(0)
        return discord.File(fp=buf, filename="meme_chart.png")

def error_embed(msg: str) -> discord.Embed:
    return discord.Embed(title="❌ Erreur", description=msg, color=0xFF6B6B)
