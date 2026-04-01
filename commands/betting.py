import os
import discord
from discord.ext import commands
from discord import app_commands
import database as db

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


def error_embed(msg: str) -> discord.Embed:
    return discord.Embed(title="❌ Erreur", description=msg, color=0xFF6B6B)
