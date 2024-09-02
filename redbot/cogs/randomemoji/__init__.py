from redbot.core.bot import Red

from .randomemoji import RandomEmoji

async def setup(bot):
    await bot.add_cog(RandomEmoji(bot))
