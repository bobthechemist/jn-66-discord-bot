import discord
from discord.ext import commands
import logging
import random
from utils.scheduler import Job
from utils.ui_helpers import create_embed, ConfirmationView, EmbedColors

log = logging.getLogger(__name__)

# This cog contains only commands. It does not need to listen to every message.
class UtilsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Example for creating a scheduled job - this one starts immediately and loops every 3 minutes
        # nuisance_job = Job(
        #     callback=self.nuisance_task,
        #     target_id=self.bot.authorized_user_id,
        #     target_type='dm',
        #     # No target_time means it starts right away
        #     minutes=3 # Frequency
        # )
        # self.bot.scheduler.add_job(nuisance_job)
        log.info('-> 🗃️ Utils cog is being initialized')

    @commands.command(description="Checks the bot's latency.")
    @commands.dm_only()
    async def ping(self, ctx: commands.Context):
        """A simple command to check if the bot is responsive."""
        latency = round(self.bot.latency * 1000) # Latency in milliseconds
        await ctx.send(f"Pong! Latency is {latency}ms.")

    @commands.command(description="Rolls a six-sided die.")
    @commands.dm_only()
    async def roll(self, ctx: commands.Context):
        """Rolls a standard die."""
        roll = random.randint(1, 6)
        await ctx.send(f"{ctx.author.mention} rolled a {roll}!")

    @commands.command(description="Shows your Discord User ID.")
    @commands.dm_only() # Using a decorator to enforce DM-only usage
    async def myid(self, ctx: commands.Context):
        """Shows your unique Discord ID. Only works in DMs."""
        await ctx.send(f"Your unique Discord User ID is: `{ctx.author.id}`")

    async def nuisance_task(self, target: discord.User):
        """A simple scheduled task for testing purposes."""
        await target.send("I'm not touching you.")
        log.info(f"Successfully sent nuisance message to {target.name}.")



# The required setup function to load the cog
async def setup(bot: commands.Bot):
    await bot.add_cog(UtilsCog(bot))