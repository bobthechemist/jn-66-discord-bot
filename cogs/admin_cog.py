# cogs/admin_cog.py
import discord
from discord.ext import commands
import logging

log = logging.getLogger(__name__)

# This cog contains commands for the bot owner to manage other cogs.
class AdminCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        log.info("-> 🤖 Admin cog is initialized.")

    # The is_owner() check is a built-in decorator that ensures only the
    # person who created the bot application can use this command.
    @commands.command(name='load', hidden=True)
    @commands.is_owner()
    async def load_cog(self, ctx: commands.Context, *, cog: str):
        """Loads a specified cog."""
        try:
            await self.bot.load_extension(f'cogs.{cog}')
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS:`** Loaded the `{cog}` cog.')

    @commands.command(name='unload', hidden=True)
    @commands.is_owner()
    async def unload_cog(self, ctx: commands.Context, *, cog: str):
        """Unloads a specified cog."""
        try:
            await self.bot.unload_extension(f'cogs.{cog}')
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS:`** Unloaded the `{cog}` cog.')

    @commands.command(name='reload', hidden=True)
    @commands.is_owner()
    async def reload_cog(self, ctx: commands.Context, *, cog: str):
        """Reloads a specified cog."""
        try:
            await self.bot.reload_extension(f'cogs.{cog}')
        except Exception as e:
            await ctx.send(f'**`ERROR:`** {type(e).__name__} - {e}')
        else:
            await ctx.send(f'**`SUCCESS:`** Reloaded the `{cog}` cog.')
            log.info(f"Cog '{cog}' was reloaded by the owner.")


# The required setup function to load the cog
async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))