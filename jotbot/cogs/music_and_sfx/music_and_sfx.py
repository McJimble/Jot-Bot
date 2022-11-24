import discord
import os

from discord.ext import commands, tasks
from ..server_only_cog import ServerOnlyCog

class MusicSFXCog(ServerOnlyCog, name = "music_and_sfx"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        pass

async def setup(bot):
    await bot.add_cog(MusicSFXCog(bot))