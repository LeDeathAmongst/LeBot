import discord
from discord.ext import commands
from redbot.core import commands
import random


class RandomEmoji(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def randomemoji(self, ctx):
        """Posts a random emoji from any server the bot has access to"""
        emojis = [emoji for guild in self.bot.guilds for emoji in guild.emojis]
        if emojis:
            emoji = random.choice(emojis)
            await ctx.send(emoji)
        else:
            await ctx.send("I don't have access to any custom emojis.")


def setup(bot):
    bot.add_cog(RandomEmoji(bot))
