import discord
import logging
import sys
from discord.ext import commands, tasks
from random import *
from jot_bot import JotBot

def read_token():
    with open("Token.txt", "r") as f:
        lines = f.readlines()
        return lines[0].strip()

def main():
    bot = JotBot()
    bot.run(read_token())


if __name__ == '__main__':
    main();