import discord
from bisect import insort
from datetime import datetime
from redbot.core import Config, checks, commands
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import bold, humanize_list, humanize_number, inline
from redbot.core.utils.menus import menu
from redbot.core.utils.views import ConfirmView
from typing import Dict, List, Union

_ = T_ = Translator("GuildManager", __file__)


@cog_i18n(_)
class GuildManager(commands.Cog):
    """Guild management tools."""

    def __init__(self, bot: Red) -> None:
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1234567890)
        default_global = {
            "whitelist": [],
            "blacklist": [],
            "serverlocked": False,
            "min_members": 0,
            "bot_ratio": 0.0,
            "log_channel": None,
        }
        self.config.register_global(**default_global)
        self.log_guild_remove = True

    @checks.is_owner()
    @commands.group(aliases=["guildman", "gman", "gm"])
    async def guildmanager(self, ctx: commands.Context):
        """Guild management commands."""
        pass

    @guildmanager.group(aliases=["wl"], invoke_without_command=True)
    async def whitelist(self, ctx: commands.Context):
        """Guild whitelist management commands."""
        whitelist = await self.config.whitelist()
        if not whitelist:
            await ctx.send_help()
            return
        embed = discord.Embed(
            title=_("Whitelisted Guilds"),
            description=humanize_list([inline(str(n)) for n in whitelist]),
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @whitelist.command(name="add")
    async def whitelist_add(self, ctx: commands.Context, *guild_ids: int):
        """Add guilds to the whitelist."""
        if not guild_ids:
            await ctx.send_help()
            return
        whitelist = await self.config.whitelist()
        blacklist = await self.config.blacklist()
        success = [n for n in guild_ids if n not in whitelist]
        async with self.config.whitelist() as wl:
            async for guild_id in AsyncIter(success):
                insort(wl, guild_id)
                if guild_id in blacklist:
                    async with blacklist as bl:
                        bl.remove(guild_id)
        failed = [n for n in guild_ids if n not in success]
        content = ""
        if success:
            content += _("The following guilds have been whitelisted: {}").format(
                humanize_list([inline(str(n)) for n in sorted(success)])
            )
        if failed:
            content += _("\nThe following guilds were already whitelisted: {}").format(
                humanize_list([inline(str(n)) for n in sorted(failed)])
            )
        await ctx.send(content=content)

    @whitelist.command(name="remove")
    async def whitelist_remove(self, ctx: commands.Context, *guild_ids: int):
        """Remove guilds from the whitelist."""
        if not guild_ids:
            await ctx.send_help()
            return
        whitelist = await self.config.whitelist()
        success = [n for n in guild_ids if n in whitelist]
        async with self.config.whitelist() as wl:
            async for guild_id in AsyncIter(success):
                wl.remove(guild_id)
        failed = [n for n in guild_ids if n not in success]
        content = ""
        if success:
            content += _("The following guilds have been removed from whitelist: {}").format(
                humanize_list([inline(str(n)) for n in sorted(success)])
            )
        if failed:
            content += _("\nThe following guilds were in the whitelist: {}").format(
                humanize_list([inline(str(n)) for n in sorted(failed)])
            )
        await ctx.send(content=content)

    @whitelist.command(name="clear")
    async def whitelist_clear(self, ctx: commands.Context):
        """Clear guilds from the whitelist."""
        await self.config.whitelist.clear()
        await ctx.send(_("The whitelist has been cleared."))

    @guildmanager.group(aliases=["bl"], invoke_without_command=True)
    async def blacklist(self, ctx: commands.Context):
        """Guild blacklist management commands."""
        blacklist = await self.config.blacklist()
        if not blacklist:
            await ctx.send_help()
            return
        embed = discord.Embed(
            title=_("Blacklisted Guilds"),
            description=humanize_list([inline(str(n)) for n in blacklist]),
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @blacklist.command(name="add")
    async def blacklist_add(self, ctx: commands.Context, *guild_ids: int):
        """Blacklist bot from joining certain guilds (autoleave)"""
        if not guild_ids:
            await ctx.send_help()
            return
        blacklist = await self.config.blacklist()
        whitelist = await self.config.whitelist()
        success = [n for n in guild_ids if n not in blacklist]
        async with self.config.blacklist() as bl:
            async for guild_id in AsyncIter(success):
                insort(bl, guild_id)
                if guild_id in whitelist:
                    async with whitelist as wl:
                        wl.remove(guild_id)
        failed = [n for n in guild_ids if n in blacklist]
        content = ""
        if success:
            content += _("The following guilds have been blacklisted: {}").format(
                humanize_list([inline(str(n)) for n in sorted(success)])
            )
        if failed:
            content += _("\nThe following guilds were already blacklisted: {}").format(
                humanize_list([inline(str(n)) for n in sorted(failed)])
            )
        await ctx.send(content=content)

    @blacklist.command(name="remove")
    async def blacklist_remove(self, ctx: commands.Context, *guild_ids: int):
        """Remove guilds from bot's blacklist."""
        if not guild_ids:
            await ctx.send_help()
            return
        blacklist = self.config.blacklist()
        success = [n for n in guild_ids if n not in blacklist]
        async with self.config.blacklist() as bl:
            async for guild_id in AsyncIter(success):
                bl.remove(guild_id)
        failed = [n for n in guild_ids if n in blacklist]
        content = ""
        if success:
            content += _("The following guilds have been blacklisted: {}").format(
                humanize_list([inline(str(n)) for n in sorted(success)])
            )
        if failed:
            content += _("\nThe following guilds were already blacklisted: {}").format(
                humanize_list([inline(str(n)) for n in sorted(failed)])
            )
        await ctx.send(content=content)

    @blacklist.command(name="clear")
    async def blacklist_clear(self, ctx: commands.Context):
        """Clear guilds from the blacklist."""
        await self.config.blacklist.clear()
        await ctx.send(_("The blacklist has been cleared."))

    @guildmanager.command()
    async def serverlock(self, ctx: commands.Context):
        """Locks [botname] to its current servers only."""
        serverlocked = await self.config.serverlocked()
        await self.config.serverlocked.set(not serverlocked)

        if serverlocked:
            await ctx.send(_("The bot is no longer serverlocked."))
        else:
            await ctx.send(_("The bot is now serverlocked."))

    @guildmanager.command()
    async def chunk(self, ctx: commands.Context, *guilds: discord.Guild):
        """Chunk unchunked guilds."""
        guilds = guilds or self.bot.guilds
        success = [g for g in guilds if not g.chunked]
        if not success:
            await ctx.send(_("All guilds are already chunked."))
            return
        async for guild in AsyncIter(success):
            await guild.chunk()
        failed = [g for g in guilds if g.chunked]
        content = _("The following guilds have been chunked: {}").format(
            humanize_list([inline(str(n)) for n in sorted(success)])
        )
        if failed:
            content += _("\nThe following guilds were already chunked: {}").format(
                humanize_list([inline(str(n)) for n in sorted(failed)])
            )
        await ctx.send(content=content)

    @guildmanager.command()
    async def channel(self, ctx: commands.Context, channel: discord.TextChannel = None):
        """Set a log channel for guild joins/leaves."""
        if channel:
            await self.config.log_channel.set(channel.id)
            await ctx.send(f"Log channel has been set to {channel.mention}.")
        else:
            await self.config.log_channel.clear()
            await ctx.send("Log channel has been removed.")

    @guildmanager.command(aliases=["minimummembers"])
    async def minmembers(self, ctx: commands.Context, min_members: int = 0):
        """
        Set how many members a server should have for the bot to stay in it.

        Pass 0 to disable.
        """
        await self.config.min_members.set(min_members)
        await ctx.send(
            _("The minimum member limit has been set to {}.").format(min_members)
            if min_members
            else _("The minimum member limit has been removed.")
        )

    @guildmanager.command()
    async def botratio(self, ctx: commands.Context, ratio: int = 0):
        """
        Set the bot ratio for servers for the bot to leave.

        The ratio must be between 0-100, pass 0 to disable.
        """
        if ratio not in range(100):
            raise commands.BadArgument(_("The ratio must be between 0 and 100."))
        rate = ratio / 100
        await self.config.bot_ratio.set(rate)
        await ctx.send(
            _("The bot ratio has been set to {}%.").format(ratio)
            if ratio
            else _("The bot ratio has been removed.")
        )

    @guildmanager.command()
    async def settings(self, ctx: commands.Context):
        """View guild manager's settings."""
        config = await self.config.all()
        log_chan = self.bot.get_channel(config["log_channel"])
        if log_chan:
            log_chan = log_chan.mention
        description = [
            f"`Log Channel     :` {log_chan}",
            f"`Minimum Members :` {config['min_members'] or '-'}",
            f"`Bot Ratio       :` {round(config['bot_ratio'] * 100) or '-'}%",
        ]
        embed = discord.Embed(
            title=_("Guild Manager Settings"),
            description="\n".join(description),
            color=await ctx.embed_color(),
        )
        await ctx.send(embed=embed)

    @guildmanager.group(aliases=["view"])
    async def show(self, ctx: commands.Context):
        """Show guilds with details."""
        pass

    @show.command(name="botfarms")
    async def show_botfarms(self, ctx: commands.Context):
        """Show bot farms."""
        config = await self.config.all()
        whitelist = config["whitelist"]
        guilds = []
        async for guild in AsyncIter(self.bot.guilds):
            bot_ratio = len([m for m in guild.members if m.bot]) / guild.member_count
            if bot_ratio >= config["bot_ratio"]:
                guilds.append(guild)
        if not guilds:
            await ctx.send(_("No bot farms found."))
            return
        fields = []
        async for guild in AsyncIter(guilds):
            guild_name = f"{guild.name}\n"
            if guild.id in whitelist:
                guild_name += _("(Whitelisted)")
            bot_ratio = len([m for m in guild.members if m.bot]) / guild.member_count
            value = _("Bot Ratio: {}").format(bold(str(round(bot_ratio * 100, 2)) + "%"))
            fields.append({"name": guild_name, "value": value, "inline": True})
        embeds = await self.pagify_embed_fields(
            *fields,
            title=_("Bot Farms ({}% Bots)").format(round(config["bot_ratio"] * 100)),
            color=discord.Color.red(),
        )
        await menu(ctx, embeds)

    @show.command(name="lessmembers")
    async def show_lessmembers(self, ctx: commands.Context):
        """Show guilds with less members than the minimum."""
        config = await self.config.all()
        whitelist = config["whitelist"]
        guilds = []
        async for guild in AsyncIter(self.bot.guilds):
            if guild.member_count < config["min_members"]:
                guilds.append(guild)
        if not guilds:
            await ctx.send(_("No servers with less members than minimum found."))
            return
        fields = []
        async for guild in AsyncIter(guilds):
            guild_name = f"{guild.name}\n"
            if guild.id in whitelist:
                guild_name += _("(Whitelisted)")
            value = _("Members: {}").format(bold(humanize_number(guild.member_count)))
            fields.append({"name": guild_name, "value": value, "inline": True})
        embeds = await self.pagify_embed_fields(
            *fields,
            title=_("Servers With Less Than {} Members)").format(config["min_members"]),
            color=discord.Color.red(),
        )
        await menu(ctx, embeds)

    @show.command()
    async def unchunked(self, ctx: commands.Context):
        """Show unchunked guilds."""
        guilds = [g for g in self.bot.guilds if not g.chunked]
        if not guilds:
            await ctx.send(_("No unchunked guilds found."))
            return
        fields = []
        async for guild in AsyncIter(guilds):
            cached = len(guild.members) / guild.member_count
            value = [
                _("Members: {}").format(bold(humanize_number(len(guild.members)))),
                _("Cached: {}").format(bold(str(round(cached * 100, 2)) + "%")),
            ]
            fields.append({"name": guild.name, "value": "\n".join(value), "inline": True})
        embeds = await self.pagify_embed_fields(
            *fields, title=_("Unchunked Guilds"), color=discord.Color.red()
        )
        await menu(ctx, embeds)

    @staticmethod
    async def pagify_embed_fields(
        *fields: Dict[str, Union[str, bool]], per_embed: int = 9, **kwargs
    ) -> List[discord.Embed]:
        embeds: List[discord.Embed] = []
        async for i in AsyncIter(range(0, len(fields), per_embed)):
            embed = discord.Embed(**kwargs)
            for field in fields[i : i + per_embed]:
                embed.add_field(**field)
            embeds.append(embed)
        async for i, embed in AsyncIter(enumerate(embeds, 1)):
            embed.set_footer(text=_("Page {}/{}").format(i, len(embeds)))
        return embeds

    @guildmanager.group()
    async def leave(self, ctx: commands.Context):
        """Leave guilds that (somehow) doesn't fulfill requirements."""
        pass

    @leave.command()
    async def blacklisted(self, ctx: commands.Context):
        """Leave guilds that are blacklisted."""
        config = await self.config.all()
        guilds = [g for g in self.bot.guilds if g.id in config["blacklist"]]
        if not guilds:
            await ctx.send(_("No blacklisted guilds found."))
            return
        view = ConfirmView(ctx.author, disable_buttons=True)
        view.message = await ctx.send(
            _("Do you want me to leave {} blacklisted guilds?").format(len(guilds)), view=view
        )
        await view.wait()
        if view.result:
            await self.leave_guilds(guilds)
            content = _("Done. I have left {} blacklisted guilds.").format(len(guilds))
            await view.message.edit(content=content)
        else:
            await view.message.edit(content=_("Ok, I won't leave any blacklisted guilds."))

    @leave.command(name="botfarms")
    async def leave_botfarms(self, ctx: commands.Context):
        """Leave bot farms."""
        config = await self.config.all()
        guilds = []
        async for guild in AsyncIter(self.bot.guilds):
            if guild.id in config["whitelist"]:
                continue
            bot_ratio = len([m for m in guild.members if m.bot]) / guild.member_count
            if bot_ratio >= config["bot_ratio"]:
                guilds.append(guild)
        if not guilds:
            await ctx.send(_("No bot farms found."))
            return
        view = ConfirmView(ctx.author, disable_buttons=True)
        view.message = await ctx.send(
            _("Do you want me to leave {} bot farms?").format(len(guilds)), view=view
        )
        await view.wait()
        if view.result:
            await self.leave_guilds(guilds)
            content = _("Done. I have left {} bot farms.").format(len(guilds))
            await view.message.edit(content=content)
        else:
            await view.message.edit(content=_("Ok, I won't leave any bot farms."))

    @leave.command(name="lessmembers")
    async def leave_lessmembers(self, ctx: commands.Context):
        """Leave guilds with less members than the minimum."""
        config = await self.config.all()
        guilds = []
        async for guild in AsyncIter(self.bot.guilds):
            if guild.id in config["whitelist"]:
                continue
            if guild.member_count < config["min_members"]:
                guilds.append(guild)
        if not guilds:
            await ctx.send(_("No servers with less members than minimum found."))
            return
        view = ConfirmView(ctx.author, disable_buttons=True)
        view.message = await ctx.send(
            _("Do you want me to leave {} servers?").format(len(guilds)), view=view
        )
        await view.wait()
        if view.result:
            await self.leave_guilds(guilds)
            content = _("Done. I have left {} servers.").format(len(guilds))
            await view.message.edit(content=content)
        else:
            await view.message.edit(content=_("Ok, I won't leave any servers."))

    @staticmethod
    async def get_system_channel(guild: discord.Guild, /):
        channel = guild.system_channel
        if not (channel and channel.permissions_for(guild.me).send_messages):
            channels = [
                c for c in guild.text_channels if c.permissions_for(guild.me).send_messages
            ]
            channel = channels[0] if channels else None
        return channel

    async def log_autoleave(self, guild: discord.Guild, title: str, reason: str):
        config = await self.config.all()
        log = self.bot.get_channel(config["log_channel"])
        if not log:
            return
        embed = discord.Embed(
            title=title,
            description=reason,
            color=discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        embed.set_author(name=f"{guild.name} ({guild.id})")
        if guild.icon:
            embed.author.icon_url = guild.icon.with_size(1024).url
        await log.send(embed=embed)

    async def leave_guilds(self, guilds: List[discord.Guild]):
        config = await self.config.all()
        async for guild in AsyncIter(guilds):
            channel = await self.get_system_channel(guild)
            if guild.id in config["blacklist"]:
                self.log_guild_remove = False
                reason = _("I'm leaving because this server is blacklisted.")
                if channel:
                    await channel.send(reason)
                await guild.leave()
                await self.log_autoleave(guild, _("Blacklisted"), reason)
                return
            min_members = config["min_members"]
            if guild.member_count < min_members:
                self.log_guild_remove = False
                reason = _("I'm leaving because this server has less than {} members.").format(
                    min_members
                )
                if channel:
                    await channel.send(reason)
                await guild.leave()
                await self.log_autoleave(guild, _("Not Enough Members"), reason)
                return
            bot_ratio = len([m for m in guild.members if m.bot]) / guild.member_count
            if bot_ratio >= config["bot_ratio"]:
                self.log_guild_remove = False
                reason = _("I'm leaving this server since it has a high bot to member ratio.")
                if channel:
                    await channel.send(reason)
                await guild.leave()
                await self.log_autoleave(guild, _("Bot Farm"), reason)

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        await self.send_to_log(guild, join=True)
        config = await self.config.all()
        if config["serverlocked"]:
            self.log_guild_remove = False
            channel = await self.get_system_channel(guild)
            reason = _("I'm leaving since I was serverlocked by my owner.")
            if channel:
                await channel.send(reason)
            await guild.leave()
            await self.log_autoleave(guild, _("Server Locked"), reason)
            return
        if guild.id in config["whitelist"]:
            return
        blacklisted = guild.id in config["blacklist"]
        bot_ratio = len([m for m in guild.members if m.bot]) / guild.member_count
        bot_farm = bot_ratio >= config["bot_ratio"]
        not_enough_members = guild.member_count < config["min_members"]
        if any([blacklisted, bot_farm, not_enough_members]):
            await self.leave_guilds([guild])

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        if self.log_guild_remove:
            await self.send_to_log(guild, join=False)
        self.log_guild_remove = True

    async def send_to_log(self, guild: discord.Guild, *, join: bool):
        config = await self.config.all()
        channel = self.bot.get_channel(config["log_channel"])
        if not channel:
            return
        created_at = discord.utils.format_dt(guild.created_at, "F")
        humans = len([m for m in guild.members if not m.bot])
        bots = len([m for m in guild.members if m.bot])
        description = [
            f"`Guild      :` {guild.name} ({guild.id})",
            f"`Owner      :` {guild.owner} ({guild.owner.id})",
            f"`Created at :` {created_at}",
            f"`Humans     :` {humans} Humans",
            f"`Bots       :` {bots} Bots",
        ]

        if join:
            title = _("I have joined a server!")
            inviter = None
            if guild.me.guild_permissions.view_audit_log:
                action = discord.AuditLogAction.bot_add
                async for log in guild.audit_logs(action=action):
                    if log.target.id == self.bot.user.id:
                        inviter = log.user
                        break
            if inviter:
                description.insert(2, f"`Invited by :` {inviter} ({inviter.id})")
        else:
            title = _("I have left a server!")

        embed = discord.Embed(
            title=title,
            description="\n".join(description),
            color=await self.bot.get_embed_color(guild),
            timestamp=datetime.utcnow(),
        )
        if guild.description:
            embed.add_field(name="Description", value=guild.description)
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.with_size(1024).url)
        if guild.splash:
            embed.set_image(url=guild.splash.with_size(4096).url)
        if guild.banner:
            embed.set_image(url=guild.banner.with_size(4096).url)
        embed.set_footer(text=f"I'm on {len(self.bot.guilds)} guilds now!")
        await channel.send(embed=embed)
