import discord
from discord.ext import commands
from discord import app_commands
import database as db
from crypto_api import get_prices


MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}


class LeaderboardCog(commands.Cog):
    """Commande /leaderboard — classement des joueurs."""

    @app_commands.command(
        name="leaderboard",
        description="Affiche le classement des meilleurs traders 🏆",
    )
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=False)

        # Récupère tous les users et leurs holdings
        all_users = await db.get_all_users()
        all_holdings = await db.get_all_holdings()

        if not all_users:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="🏆 Leaderboard",
                    description="Aucun joueur enregistré pour l'instant.",
                    color=0xF1C40F,
                )
            )
            return

        # Récupère tous les symboles uniques pour un seul appel API
        all_symbols = list({h["crypto_id"] for h in all_holdings})
        prices = await get_prices(all_symbols) if all_symbols else {}

        # Calcule la valeur totale de chaque user
        # Construit un index holdings par user_id
        holdings_by_user: dict[str, list[dict]] = {}
        for h in all_holdings:
            holdings_by_user.setdefault(h["user_id"], []).append(h)

        rankings = []
        for user in all_users:
            uid = user["user_id"]
            cash = user["balance"]
            portfolio_value = sum(
                h["amount"] * (prices.get(h["crypto_id"]) or 0.0)
                for h in holdings_by_user.get(uid, [])
            )
            rankings.append(
                {
                    "user_id": uid,
                    "username": user["username"],
                    "cash": cash,
                    "portfolio": portfolio_value,
                    "total": cash + portfolio_value,
                }
            )

        rankings.sort(key=lambda x: x["total"], reverse=True)
        top10 = rankings[:10]

        caller_id = str(interaction.user.id)
        caller_rank = next(
            (i + 1 for i, r in enumerate(rankings) if r["user_id"] == caller_id), None
        )

        lines = []
        for i, entry in enumerate(top10, start=1):
            medal = MEDALS.get(i, f"`#{i}`")
            name = entry["username"]
            total = entry["total"]
            is_caller = entry["user_id"] == caller_id
            arrow = " ◀ toi" if is_caller else ""
            lines.append(f"{medal} **{name}** — **${total:,.2f}**{arrow}")

        description = "\n".join(lines)

        # Si l'appelant est hors top 10, on l'ajoute en bas
        if caller_rank and caller_rank > 10:
            caller_data = next(r for r in rankings if r["user_id"] == caller_id)
            description += (
                f"\n\n─────────────\n"
                f"`#{caller_rank}` **{caller_data['username']}** "
                f"— **${caller_data['total']:,.2f}** ◀ toi"
            )

        embed = discord.Embed(
            title="🏆 Classement des traders",
            description=description,
            color=0xF1C40F,
        )
        embed.set_footer(text=f"{len(rankings)} joueur(s) enregistré(s)")

        await interaction.followup.send(embed=embed)
