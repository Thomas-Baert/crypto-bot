import os
import io
import discord
from discord.ext import commands
from discord import app_commands
import database as db
import matplotlib.pyplot as plt
import asyncio

class BettingCog(commands.Cog):
    """Commandes liées aux paris événementiels (Soutenance de Lilian)."""

    def __init__(self, bot):
        self.bot = bot

    # ─── /pari ───────────────────────────────────────────────────────────────

    pari_group = app_commands.Group(name="pari", description="Paris sur la note de soutenance de Lilian")

    @pari_group.command(name="exact", description="[Cote x10] Parie sur la note exacte (0-20)")
    @app_commands.describe(note="La note exacte (ex: 15.5)", montant="Le montant à parier")
    async def bet_exact(self, interaction: discord.Interaction, note: float, montant: float):
        await self._place_bet(interaction, montant, "exact", note)

    @pari_group.command(name="min", description="[Cote x2] Parie que la note sera AU MOINS celle-ci")
    @app_commands.describe(note="La note minimale", montant="Le montant à parier")
    async def bet_min(self, interaction: discord.Interaction, note: float, montant: float):
        await self._place_bet(interaction, montant, "min", note)

    @pari_group.command(name="max", description="[Cote x2] Parie que la note sera AU PLUS celle-ci")
    @app_commands.describe(note="La note maximale", montant="Le montant à parier")
    async def bet_max(self, interaction: discord.Interaction, note: float, montant: float):
        await self._place_bet(interaction, montant, "max", note)

    @pari_group.command(name="intervalle", description="[Cote x3] Parie que la note sera entre min et max")
    @app_commands.describe(note_min="Note minimale", note_max="Note maximale", montant="Mise")
    async def bet_intervalle(self, interaction: discord.Interaction, note_min: float, note_max: float, montant: float):
        if note_min >= note_max:
            await interaction.response.send_message(
                embed=error_embed("La note minimum doit être strictement inférieure à la note maximum !"),
                ephemeral=True
            )
            return
        await self._place_bet(interaction, montant, "intervalle", note_min, note_max)

    async def _place_bet(self, interaction: discord.Interaction, montant: float, bet_type: str, val1: float, val2: float = None):
        # Validation de la note
        if val1 < 0 or val1 > 20 or (val2 is not None and (val2 < 0 or val2 > 20)):
            await interaction.response.send_message(
                embed=error_embed("La note de Lilian doit être comprise entre 0 et 20 !"),
                ephemeral=True
            )
            return

        # Validation du montant
        if montant <= 0:
            await interaction.response.send_message(
                embed=error_embed("Le montant du pari doit être supérieur à 0 !"),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)
        
        user = await db.get_or_create_user(interaction.user.id, interaction.user.display_name)
        if user["balance"] < montant:
            await interaction.followup.send(
                embed=error_embed(f"Solde insuffisant !\nTon solde cash: **${user['balance']:,.2f}**")
            )
            return

        # Retirer l'argent
        new_balance = user["balance"] - montant
        await db.update_balance(interaction.user.id, new_balance)

        # Enregistrer le pari
        await db.place_lilian_bet(interaction.user.id, montant, bet_type, val1, val2)

        embed = discord.Embed(
            title="🎰 Pari enregistré !",
            color=0x9B59B6
        )
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.display_avatar.url)
        embed.add_field(name="💸 Mise", value=f"**${montant:,.2f}**", inline=True)
        
        if bet_type == "exact":
            condition = f"Exactement **{val1}/20**"
            gains = montant * 10
        elif bet_type == "min":
            condition = f"Au moins **{val1}/20**"
            gains = montant * 2
        elif bet_type == "max":
            condition = f"Au plus **{val1}/20**"
            gains = montant * 2
        else: # intervalle
            condition = f"Entre **{val1}** et **{val2}/20**"
            gains = montant * 3
            
        embed.add_field(name="🎯 Condition", value=condition, inline=True)
        embed.add_field(name="💰 Gains potentiels", value=f"**${gains:,.2f}**", inline=True)
        embed.add_field(name="💵 Nouveau solde", value=f"**${new_balance:,.2f}**", inline=False)
        embed.set_footer(text="En attente des résultats de la soutenance...")

        await interaction.followup.send(embed=embed)


    # ─── /resultat_lilian ────────────────────────────────────────────────────

    @app_commands.command(
        name="resultat_lilian",
        description="[ADMIN/OWNER] Résout tous les paris sur la note de Lilian"
    )
    @app_commands.describe(note_finale="La note finale exacte obtenue par Lilian (ex: 16.5)")
    async def resultat_lilian(self, interaction: discord.Interaction, note_finale: float):
        # Vérification des droits: Soit OWNER_ID défini dans .env, soit Administrator.
        owner_id = os.getenv("OWNER_ID")
        is_owner = owner_id and str(interaction.user.id) == str(owner_id)
        is_admin = interaction.user.guild_permissions.administrator

        if not (is_owner or is_admin):
             await interaction.response.send_message(
                 embed=error_embed("Tu n'as pas l'autorisation de sceller le destin de Lilian !"),
                 ephemeral=True
             )
             return

        if note_finale < 0 or note_finale > 20:
            await interaction.response.send_message(
                embed=error_embed("La note finale doit être entre 0 et 20 !"),
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=False)

        all_bets = await db.get_all_lilian_bets()
        if not all_bets:
            await interaction.followup.send("🎊 La note de Lilian est tombée, mais personne n'avait fait de pari !")
            return

        winners = []
        total_payout = 0

        for bet in all_bets:
            uid = bet["user_id"]
            amount = bet["amount"]
            btype = bet["bet_type"]
            val1 = bet["val1"]
            val2 = bet["val2"]

            won = False
            payout = 0
            if btype == "exact" and note_finale == val1:
                won = True
                payout = amount * 10
            elif btype == "min" and note_finale >= val1:
                won = True
                payout = amount * 2
            elif btype == "max" and note_finale <= val1:
                won = True
                payout = amount * 2
            elif btype == "intervalle" and val1 <= note_finale <= val2:
                won = True
                payout = amount * 3

            if won:
                # Ajoute le paiement
                user = await db.get_or_create_user(uid, "Unknown") # Username won't update here
                new_balance = user["balance"] + payout
                await db.update_balance(uid, new_balance)
                winners.append((uid, payout))
                total_payout += payout

        await db.clear_lilian_bets()

        # Annonce
        embed = discord.Embed(
            title=f"🎓 Les résultats de Lilian sont là !",
            description=f"La note finale de la soutenance est de **{note_finale}/20** !\n\n",
            color=0xF1C40F
        )
        
        if winners:
            winners_text = ""
            for uid, payout in winners:
                winners_text += f"• <@{uid}> remporte **${payout:,.2f}**\n"
            embed.description += f"**🏆 Les Gagnants :**\n{winners_text}"
        else:
            embed.description += "💔 Personne n'a eu juste ! Les serveurs du bot s'engraissent avec vos mises."

        embed.set_footer(text=f"Total de gains reversés : ${total_payout:,.2f}")
        await interaction.followup.send(embed=embed)

    # ─── /pari liste (Graphique) ─────────────────────────────────────────────

    @pari_group.command(name="liste", description="📊 Affiche un diagramme bâton des paris en cours")
    async def liste_paris(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)
        all_bets = await db.get_all_lilian_bets()
        
        if not all_bets:
            await interaction.followup.send(embed=error_embed("Aucun pari n'a encore été enregistré sur la note de Lilian !"))
            return

        total_pool = sum(b['amount'] for b in all_bets)
        
        try:
            file = await asyncio.to_thread(self._generate_bar_chart, all_bets)
            embed = discord.Embed(
                title="📊 Répartition des Paris",
                description=f"Voici la répartition mathématique des probabilités selon les mises des joueurs.\n\n💰 **Cagnotte Totale en jeu : ${total_pool:,.2f}**",
                color=0x3498DB
            )
            embed.set_image(url="attachment://bet_distribution.png")
            embed.set_footer(text="Généré avec matplotlib • Les paris d'intervalle sont répartis équitablement")
            await interaction.followup.send(embed=embed, file=file)
        except Exception as e:
            await interaction.followup.send(embed=error_embed(f"Erreur lors de la génération du diagramme : {e}"))

    def _generate_bar_chart(self, all_bets: list[dict]) -> discord.File:
        """Dessine un diagramme en bâtons avec matplotlib et le renvoie sous forme de fichier discord."""
        # Initialise les montants à 0 pour chaque note de 0 à 20
        amounts_by_note = {i: 0.0 for i in range(21)}

        for bet in all_bets:
            amt = bet["amount"]
            btype = bet["bet_type"]
            val1 = bet["val1"]
            val2 = bet["val2"]

            # L'axe X n'affiche que des entiers (0, 1, ..., 20)
            v1_int = int(round(val1))
            v2_int = int(round(val2)) if val2 is not None else None

            if btype == "exact":
                if 0 <= v1_int <= 20:
                    amounts_by_note[v1_int] += amt
            elif btype == "min":
                v1_int = max(0, v1_int)
                spread_count = 20 - v1_int + 1
                if spread_count > 0:
                    spread_amt = amt / spread_count
                    for i in range(v1_int, 21):
                        amounts_by_note[i] += spread_amt
            elif btype == "max":
                v1_int = min(20, v1_int)
                spread_count = v1_int + 1
                if spread_count > 0:
                    spread_amt = amt / spread_count
                    for i in range(0, v1_int + 1):
                        amounts_by_note[i] += spread_amt
            elif btype == "intervalle":
                v1_int = max(0, v1_int)
                v2_int = min(20, v2_int)
                if v1_int <= v2_int:
                    spread_count = v2_int - v1_int + 1
                    spread_amt = amt / spread_count
                    for i in range(v1_int, v2_int + 1):
                        amounts_by_note[i] += spread_amt

        x = list(amounts_by_note.keys())
        y = list(amounts_by_note.values())

        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        
        # Couleur de fond type Discord Dark Theme
        discord_bg = '#2b2d31'
        fig.patch.set_facecolor(discord_bg)
        ax.set_facecolor(discord_bg)

        # Dessin des bâtons (Dorés)
        bars = ax.bar(x, y, color='#F1C40F', edgecolor='#e67e22', zorder=3)
        
        ax.set_title("Répartition de l'argent misé sur chaque note", color='white', fontsize=14, pad=15)
        ax.set_xlabel("Notes (de 0 à 20)", color='#b9bbbe', fontsize=12)
        ax.set_ylabel("Total Parié Équivalent ($)", color='#b9bbbe', fontsize=12)
        ax.set_xticks(range(21))
        
        # Design et nettoyage
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_color('#8e9297')
        ax.spines['bottom'].set_color('#8e9297')
        ax.tick_params(colors='#8e9297')
        ax.grid(axis='y', linestyle='--', alpha=0.2, zorder=0)

        # Ajout des valeurs au-dessus des barres
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(f'${height:,.0f}',
                            xy=(bar.get_x() + bar.get_width() / 2, height),
                            xytext=(0, 3),  
                            textcoords="offset points",
                            ha='center', va='bottom', color='white', fontsize=9)

        # Copie dans la RAM
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=120)
        plt.close(fig)
        buf.seek(0)
        
        return discord.File(fp=buf, filename="bet_distribution.png")


def error_embed(msg: str) -> discord.Embed:
    return discord.Embed(title="❌ Erreur", description=msg, color=0xFF6B6B)
