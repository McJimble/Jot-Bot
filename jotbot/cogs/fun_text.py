import discord

from discord.ext import commands
from random import *

from .server_only_cog import *

vowels = ['a', 'e', 'i', 'o', 'u']
exclude = ["the", "i\'m", "and"]
markdownSymbols = ["*", "**", "***", "__", "~~", "`", "__*", "__**", "__***", "<", ">", ";", "'", "!"]
excludefirsts = ['w']
locFileName = "res/Locations.txt"

# Generic text commands that are not very useful
class FunTextCog(ServerOnlyCog, name = "Fun Text"):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.locations_def = str()
        self.reread_loc_file()

    def reread_loc_file(self):
        with open(locFileName, "r") as locFile:
            self.fortnitelocations_def = locFile.readlines()
            locFile.close()

    def letterify(self, originalStr, replace: str):
        words = originalStr
        finalJimmify = []
        for word in words:
            if len(word) <= 0:
                continue

            if len(word) > 2 and word[0].lower() != replace and word.lower() not in exclude and word[0].lower() not in excludefirsts:
                
                # Brute-force check for markdown/symbols to skip in the word
                markDownEnd = 0
                wordLen = len(word)
                while not word[markDownEnd].isalpha() and markDownEnd < wordLen:
                    markDownEnd += 1

                # Replace first letter in the string.
                # If it's capitalized, capitalize the replacement letter and lower the old one.
                jRep = replace.upper() if word[markDownEnd].isupper() else replace
                if word[markDownEnd].lower() in vowels:
                    if word[markDownEnd].islower():
                        word = word[0:markDownEnd] + jRep + word[markDownEnd:-1] + word[-1]
                    else:
                        word = word[0:markDownEnd] + jRep + word[markDownEnd].lower() + word[markDownEnd+1:-1] + word[-1]
                else:
                    word = word.replace(word[markDownEnd], jRep, 1)

            finalJimmify.append(word)

        return finalJimmify


    @commands.command(name='Jimmify')
    async def jimmify(self, ctx, *args):

        msg = str(ctx.message.content).split(' ')
        msg.pop(0)
        if len(args) == 0:
            msg = [message async for message in ctx.channel.history(limit=2)]
            msg = msg[1].content.split(' ')

        finalJimmify = self.letterify(msg, 'j')
        await ctx.send(" ".join(finalJimmify))

    @commands.command(name='Mattify')
    async def mattify(self, ctx, *args):

        msg = str(ctx.message.content).split(' ')
        msg.pop(0)
        if len(args) == 0:
            msg = [message async for message in ctx.channel.history(limit=2)]
            msg = msg[1].content.split(' ')

        finalJimmify = self.letterify(msg, 'm')
        await ctx.send(" ".join(finalJimmify))

    @commands.command(name='Droppin')
    async def droppin(self, ctx):
        val = randint(0, len(self.fortnitelocations_def) - 1)
        await ctx.send(self.fortnitelocations_def[val])
        pass

    @commands.command(name='SetDroppin')
    async def set_droppin(self, ctx, *args):

        if args == None:
            await ctx.send("Error: no locations given with command. Locations are unchanged.")
            return

        final = []
        for i in range(len(args)):
            final.append(args[i] + "\n")

        print(final)
        with open (locFileName, "w") as locFile:
            locFile.writelines(final)
            locFile.close()

        self.reread_loc_file()
        await ctx.send("Locations list successfully overwritten and changed to: \n" + ", ".join(args))

    @commands.command(name='AddDroppin')
    async def add_droppin(self, ctx, *args):
        if args == None:
            await ctx.send("Error: no locations given with command. Locations are unchanged.")
            return

        toAdd = " ".join(args).strip()
        with open(locFileName, "a") as locFile:
            locFile.writelines(["\n", f"{toAdd}"])
            locFile.close()

        self.reread_loc_file()
        await ctx.send(f"Added {toAdd} to locations list")

    @commands.command(name='RemoveDroppin')
    async def remove_droppin(self, ctx, *args):

        original = " ".join(args)
        toRem = original.lower()
        ind = None

        locs = self.fortnitelocations_def.copy()
        for i in range(len(locs)):
            locs[i] = locs[i].lower().strip("\n")

        try:
            locs.index(toRem)
        except ValueError as e:
            await ctx.send(f'Could not find: {toRem} in droppin list!')
            return
        else:
            ind = locs.index(toRem)
            self.fortnitelocations_def.pop(ind)
        
        with open(locFileName, "w") as locFile:
            locFile.writelines(self.fortnitelocations_def)
            locFile.close()

        await ctx.send(f"Successfully removed the location: {original}")

    @commands.command(name='ShowDroppin')
    async def show_droppin(self, ctx):

        toPrint = self.fortnitelocations_def
        if randint(1, 1000) == 1:
            secrets = ["Jimmy Junction", "Matt Mansion"]
            val = randint(0, len(secrets))
            toPrint = secrets[val]


        await ctx.send("Current droppin' locations: \n" + "".join(toPrint))


async def setup(bot):
    await bot.add_cog(FunTextCog(bot))