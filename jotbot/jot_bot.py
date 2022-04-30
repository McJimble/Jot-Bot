import discord
import logging
from discord.ext import commands, tasks
from random import *

class JotBot(commands.Bot):

    def __init__(self):

        super().__init__(command_prefix='!', case_insensitive=True)

        # If this bot got any bigger, probably don't want to do this but whatever.
        self.extensions_def = ['cogs.fun_text', 'cogs.jasino.jasino']

        for extension in self.extensions_def:
            try:
                self.load_extension(extension)
            except Exception as e:
                print(f'Could not load extension: {extension}')
                print(e)
            else:
                print(f'Successfully loaded extension: {extension}')

    # Handle generic things for any non-command messages
    async def on_message(self, message):
        if message.author == self.user:
            return

        await self.process_commands(message)

        # Funny test-server specific inside joke; done quick and easy bc it's stupid
        #if message.author.display_name == 'tagtart':
        #        if message.channel.id == 959292791777812520:
        #            await message.channel.send('Adam Moment.')

    async def on_ready(self):
        print('We have logged in as {0.user}'.format(self))
        logging.basicConfig(level=logging.INFO)