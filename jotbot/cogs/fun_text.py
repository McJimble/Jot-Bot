import discord
from discord.ext import commands
from random import *

vowels = ['a', 'e', 'i', 'o', 'u']
exclude = ["the", "i\'m", "and"]
excludefirsts = ['w']
locFileName = "res/Locations.txt"

# Generic text commands that are not very useful
class FunTextCog(commands.Cog, name = "Fun Text"):

    def __init__(self, bot):
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
        print(words)
        for word in words:
            if len(word) <= 0:
                continue

            if len(word) > 2 and word[0].lower() != replace and word.lower() not in exclude and word[0].lower() not in excludefirsts:
                jRep = replace.upper() if word[0].isupper() else replace

                if word[0].lower() in vowels:
                    if word.isupper():
                        word = jRep + word
                    else:
                        word = jRep + word[0].lower() + word[1:len(word)]
                else:
                    word = word.replace(word[0], jRep, 1)

            finalJimmify.append(word)

        return finalJimmify


    @commands.command()
    async def jimmify(self, ctx, *args):

        msg = str(ctx.message.content).split(' ')
        msg.pop(0)
        if len(args) == 0:
            msg = await ctx.channel.history(limit=2).flatten()
            msg = msg[1].content.split(' ')

        finalJimmify = self.letterify(msg, 'j')
        await ctx.send(" ".join(finalJimmify))

    @commands.command()
    async def mattify(self, ctx, *args):

        msg = str(ctx.message.content).split(' ')
        msg.pop(0)
        if len(args) == 0:
            msg = await ctx.channel.history(limit=2).flatten()
            msg = msg[1].content.split(' ')

        finalJimmify = self.letterify(msg, 'm')
        await ctx.send(" ".join(finalJimmify))

    @commands.command()
    async def droppin(self, ctx):
        val = randint(0, len(self.fortnitelocations_def) - 1)
        await ctx.send(self.fortnitelocations_def[val])
        pass

    @commands.command()
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

    @commands.command()
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

    @commands.command()
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

    @commands.command()
    async def show_droppin(self, ctx):

        toPrint = self.fortnitelocations_def
        if randint(1, 1000) == 1:
            secrets = ["Jimmy Junction", "Matt Mansion"]
            val = randint(0, len(secrets))
            toPrint = secrets[val]


        await ctx.send("Current droppin' locations: \n" + "".join(toPrint))


def setup(bot):
    bot.add_cog(FunTextCog(bot))