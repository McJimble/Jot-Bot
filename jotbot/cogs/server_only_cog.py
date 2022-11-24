from discord.ext import commands, tasks

# TODO: If more common functionality is needed between cogs, refactor this into a 
# BaseCog class, with the server only being a specific attribute that can be set in the constructor.
# (Possibly with a dictionary of all attributes to set via key/val pairs)

# Most cogs are specific to individual servers and can only be called inside a server rather than DMs
class ServerOnlyCog(commands.Cog):

    async def cog_check(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send('This command cannot be used in DM channels\n')
            return False

        return True