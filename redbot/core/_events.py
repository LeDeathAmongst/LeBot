import asyncio
import contextlib
import platform
import socket
import random
import sys
import logging
import traceback
from rich.console import Console
from rich.errors import MarkupError
from datetime import datetime, timedelta, timezone
from typing import Tuple

import aiohttp
import discord
import importlib.metadata
from packaging.requirements import Requirement
from redbot.core import data_manager
from redbot.core.bot import ExitCodes
from redbot.core.commands import RedHelpFormatter, HelpSettings
from redbot.core.i18n import (
    Translator,
    set_contextual_locales_from_guild,
)

from .. import __version__ as red_version, version_info as red_version_info
from . import commands
from .config import get_latest_confs
from .utils._internal_utils import (
    fuzzy_command_search,
    format_fuzzy_results,
    expected_version,
    fetch_latest_red_version_info,
    send_to_owners_with_prefix_replaced,
)
from .utils.chat_formatting import box as code, error as cross, format_perms_list

import psutil
import shutil

import rich
from rich import box
from rich.table import Table
from rich.columns import Columns
from rich.panel import Panel
from rich.text import Text

log = logging.getLogger("red")

INTRO = r"""

       ...              s                                         .                                     ..                           ...              s                             
   .x888888hx    :     :8                               oec :    @88>                             . uW8"        ..               .x888888hx    :     :8                             
  d88888888888hxx     .88                   .u    .    @88888    %8P      .u    .                 `t888        @L               d88888888888hxx     .88                   .u    .   
 8" ... `"*8888%`    :888ooo       u      .d88B :@8c   8"*88%     .     .d88B :@8c       .u        8888   .   9888i   .dL      8" ... `"*8888%`    :888ooo       u      .d88B :@8c  
!  "   ` .xnxx.    -*8888888    us888u.  ="8888f8888r  8b.      .@88u  ="8888f8888r   ud8888.      9888.z88N  `Y888k:*888.    !  "   ` .xnxx.    -*8888888    us888u.  ="8888f8888r 
X X   .H8888888%:    8888    .@88 "8888"   4888>'88"  u888888> ''888E`   4888>'88"  :888'8888.     9888  888E   888E  888I    X X   .H8888888%:    8888    .@88 "8888"   4888>'88"  
X 'hn8888888*"   >   8888    9888  9888    4888> '     8888R     888E    4888> '    d888 '88%"     9888  888E   888E  888I    X 'hn8888888*"   >   8888    9888  9888    4888> '    
X: `*88888%`     !   8888    9888  9888    4888>       8888P     888E    4888>      8888.+"        9888  888E   888E  888I    X: `*88888%`     !   8888    9888  9888    4888>      
'8h.. ``     ..x8>  .8888Lu= 9888  9888   .d888L .+    *888>     888E   .d888L .+   8888L          9888  888E   888E  888I    '8h.. ``     ..x8>  .8888Lu= 9888  9888   .d888L .+   
 `88888888888888f   ^%888*   9888  9888   ^"8888*"     4888      888&   ^"8888*"    '8888c. .+    .8888  888"  x888N><888'     `88888888888888f   ^%888*   9888  9888   ^"8888*"    
  '%8888888888*"      'Y"    "888*""888"     "Y"       '888      R888"     "Y"       "88888%       `%888*%"     "88"  888       '%8888888888*"      'Y"    "888*""888"     "Y"      
     ^"****""`                ^Y"   ^Y'                 88R       ""                   "YP'           "`              88F          ^"****""`                ^Y"   ^Y'               
                                                        88>                                                          98"                                                            
                                                        48                                                         ./"                                                              
                                                        '8                                                        ~`                                                                

"""

_ = Translator(__name__, __file__)

# Example function to create a rainbow gradient text
def gradient_text(text, colors):
    """Create a gradient effect for text by cycling through the given colors."""
    gradient = Text()
    for i, char in enumerate(text):
        gradient.append(char, style=colors[i % len(colors)])
    return gradient


def get_holiday_colors():
    today = datetime.now().date()
    holiday_colors = {
        "Christmas": ["red", "green", "gold", "white"],
        "Halloween": ["orange", "black", "purple", "green"],
        "Thanksgiving": ["orange", "brown", "yellow", "red"],
        "Valentine's Day": ["red", "pink", "white", "purple"],
        "St. Patrick's Day": ["green", "gold", "white", "orange"],
        "New Year's Day": ["gold", "silver", "black", "white"],
    }

    if datetime(today.year, 12, 20).date() <= today <= datetime(today.year, 12, 28).date():
        return holiday_colors["Christmas"]
    elif datetime(today.year, 10, 26).date() <= today <= datetime(today.year, 11, 5).date():
        return holiday_colors["Halloween"]
    elif datetime(today.year, 11, 20).date() <= today <= datetime(today.year, 11, 30).date():
        return holiday_colors["Thanksgiving"]
    elif datetime(today.year, 2, 10).date() <= today <= datetime(today.year, 2, 17).date():
        return holiday_colors["Valentine's Day"]
    elif datetime(today.year, 3, 14).date() <= today <= datetime(today.year, 3, 22).date():
        return holiday_colors["St. Patrick's Day"]
    elif datetime(today.year, 12, 28).date() <= today <= datetime(today.year + 1, 1, 4).date():
        return holiday_colors["New Year's Day"]

    # Default colors if no holiday is active
    return ["blue", "white", "gray"]


def get_disk_usage():
    total, used, free = shutil.disk_usage("/")
    return {
        "Total": f"{total // (2**30)} GB",
        "Used": f"{used // (2**30)} GB",
        "Free": f"{free // (2**30)} GB",
        "Usage Percentage": f"{used / total * 100:.2f}%",
    }


def get_resource_usage():
    # CPU usage percentage
    cpu_usage = psutil.cpu_percent(interval=1)
    # Memory usage
    memory_info = psutil.virtual_memory()
    memory_usage = {
        "Total": f"{memory_info.total // (2**20)} MB",
        "Used": f"{memory_info.used // (2**20)} MB",
        "Free": f"{memory_info.free // (2**20)} MB",
        "Usage Percentage": f"{memory_info.percent}%",
    }

    return {"CPU Usage": f"{cpu_usage}%", "Memory Usage": memory_usage}


def init_events(bot, cli_flags):
    @bot.event
    async def on_connect():
        if bot._uptime is None:
            log.info("Connected to Discord. Getting ready...")

    @bot.event
    async def on_ready():
        try:
            await _on_ready()
        except Exception as exc:
            log.critical("The bot failed to get ready!", exc_info=exc)
            sys.exit(ExitCodes.CRITICAL)

    async def _on_ready():
        if bot._uptime is not None:
            return

        bot._uptime = discord.utils.utcnow()

        guilds = len(bot.guilds)
        users = len(set([m for m in bot.get_all_members()]))

        invite_url = discord.utils.oauth_url(bot.application_id, scopes=("bot"))

        prefixes = cli_flags.prefix or (await bot._config.prefix())
        lang = await bot._config.locale()
        dpy_version = discord.__version__
        red_creator = "Star (a.k.a. Rosie)"
        host_company = "Shadow ~ Hosting"

        unique_users = len({member.id for guild in bot.guilds for member in guild.members})

        app_info = await bot.application_info()
        owner_names = app_info.owner.name

        table_general_info = Table(show_edge=False, show_header=False, box=box.MINIMAL)
        table_general_info.add_row("Prefixes", ", ".join(prefixes))
        table_general_info.add_row("Language", lang)
        table_general_info.add_row("Red version", red_version)
        table_general_info.add_row("Discord.py version", dpy_version)
        table_general_info.add_row("Storage type", data_manager.storage_type())

        table_bot_info = Table(show_edge=False, show_header=False, box=box.MINIMAL)
        table_bot_info.add_row("Owner", owner_names)
        table_bot_info.add_row("Developer", owner_names)
        table_bot_info.add_row("Created By", red_creator)
        table_bot_info.add_row("Hosted On", host_company)

        disk_usage = get_disk_usage()
        resource_usage = get_resource_usage()

        table_resource_usage = Table(show_edge=False, show_header=False, box=box.MINIMAL)
        table_resource_usage.add_column("Resource", justify="left")
        table_resource_usage.add_column("Total", justify="right")
        table_resource_usage.add_column("Used", justify="right")
        table_resource_usage.add_column("Free", justify="right")
        table_resource_usage.add_column("Usage Percentage", justify="right")
        table_resource_usage.add_row("CPU", "-", f"{resource_usage['CPU Usage']}", "-", "-")
        table_resource_usage.add_row(
            "Memory",
            resource_usage["Memory Usage"]["Total"],
            resource_usage["Memory Usage"]["Used"],
            resource_usage["Memory Usage"]["Free"],
            resource_usage["Memory Usage"]["Usage Percentage"],
        )
        table_resource_usage.add_row(
            "Disk",
            disk_usage["Total"],
            disk_usage["Used"],
            disk_usage["Free"],
            disk_usage["Usage Percentage"],
        )

        table_counts = Table(show_edge=False, show_header=False, box=box.MINIMAL)
        table_counts.add_row("Shards", str(bot.shard_count))
        table_counts.add_row("Servers", str(guilds))
        if bot.intents.members:
            table_counts.add_row("Total Users", str(users))
        table_counts.add_row("Unique Users", str(unique_users))

        pypi_version, py_version_req = await fetch_latest_red_version_info()

        rich_console = rich.get_console()
        rich_console.print(INTRO, style="dark_slate_gray2", markup=False, highlight=False)
        if guilds:
            rich_console.print(
                Columns(
                    [
                        Panel(
                            table_general_info,
                            title=gradient_text(bot.user.display_name, get_holiday_colors()),
                        ),
                        Panel(
                            table_counts,
                            title=gradient_text(bot.user.display_name, get_holiday_colors()),
                        ),
                        Panel(
                            table_bot_info,
                            title=gradient_text(bot.user.display_name, get_holiday_colors()),
                        ),
                        Panel(
                            table_resource_usage,
                            title=gradient_text(bot.user.display_name, get_holiday_colors()),
                        ),
                    ],
                    equal=True,
                    align="center",
                )
            )
        else:
            rich_console.print(
                Columns(
                    [
                        Panel(
                            table_general_info,
                            title=gradient_text(bot.user.display_name, ["blue", "magenta"]),
                        )
                    ]
                )
            )

        rich_console.print(
            "Loaded {} cogs with {} commands".format(len(bot.cogs), len(bot.commands))
        )

        if invite_url:
            rich_console.print(f"\nInvite URL: {Text(invite_url, style=f'link {invite_url}')}")
            # We generally shouldn't care if the client supports it or not as Rich deals with it.
        if not guilds:
            rich_console.print(
                f"Looking for a quick guide on setting up LeBot? Contact death_waffle on Discord for assistance!"
            )
        bot._red_ready.set()

    @bot.event
    async def on_command_completion(ctx: commands.Context):
        await bot._delete_delay(ctx)

    @bot.event
    async def on_command_error(ctx: commands.Context, error, unhandled_by_cog=False):
        if not unhandled_by_cog:
            if hasattr(ctx.command, "on_error"):
                return
            if ctx.cog and ctx.cog.has_error_handler():
                return
        if not isinstance(error, commands.CommandNotFound):
            asyncio.create_task(bot._delete_delay(ctx))
        converter = getattr(ctx.current_parameter, "converter", None)
        argument = ctx.current_argument
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send_help()
        elif isinstance(error, commands.ArgParserFailure):
            msg = cross(_("`{user_input}` is not a valid value for `{command}`")).format(
                user_input=error.user_input, command=error.cmd
            )
            if error.custom_help_msg:
                msg += f"\n{error.custom_help_msg}"
            try:
                await ctx.reply(msg, mention_author=False)
            except discord.HTTPException:
                await ctx.send(msg)
            if error.send_cmd_help:
                await ctx.send_help()
        elif isinstance(error, commands.RangeError):
            if isinstance(error.value, int):
                if error.minimum == 0 and error.maximum is None:
                    message = _("Argument `{parameter_name}` must be a positive integer.")
                elif error.minimum is None and error.maximum is not None:
                    message = _(
                        "Argument `{parameter_name}` must be an integer no more than {maximum}."
                    )
                elif error.minimum is not None and error.maximum is None:
                    message = _(
                        "Argument `{parameter_name}` must be an integer no less than {minimum}."
                    )
                elif error.maximum is not None and error.minimum is not None:
                    message = _(
                        "Argument `{parameter_name}` must be an integer between {minimum} and {maximum}."
                    )
            elif isinstance(error.value, float):
                if error.minimum == 0 and error.maximum is None:
                    message = _("Argument `{parameter_name}` must be a positive number.")
                elif error.minimum is None and error.maximum is not None:
                    message = _(
                        "Argument `{parameter_name}` must be a number no more than {maximum}."
                    )
                elif error.minimum is not None and error.maximum is None:
                    message = _(
                        "Argument `{parameter_name}` must be a number no less than {maximum}."
                    )
                elif error.maximum is not None and error.minimum is not None:
                    message = _(
                        "Argument `{parameter_name}` must be a number between {minimum} and {maximum}."
                    )
            elif isinstance(error.value, str):
                if error.minimum is None and error.maximum is not None:
                    message = _(
                        "Argument `{parameter_name}` must be a string with a length of no more than {maximum}."
                    )
                elif error.minimum is not None and error.maximum is None:
                    message = _(
                        "Argument `{parameter_name}` must be a string with a length of no less than {minimum}."
                    )
                elif error.maximum is not None and error.minimum is not None:
                    message = _(
                        "Argument `{parameter_name}` must be a string with a length of between {minimum} and {maximum}."
                    )
            await ctx.send(
                message.format(
                    maximum=error.maximum,
                    minimum=error.minimum,
                    parameter_name=ctx.current_parameter.name,
                )
            )
            return
        elif isinstance(error, commands.BadArgument):
            if isinstance(converter, commands.Range):
                if converter.annotation is int:
                    if converter.min == 0 and converter.max is None:
                        message = _("Argument `{parameter_name}` must be a positive integer.")
                    elif converter.min is None and converter.max is not None:
                        message = _(
                            "Argument `{parameter_name}` must be an integer no more than {maximum}."
                        )
                    elif converter.min is not None and converter.max is None:
                        message = _(
                            "Argument `{parameter_name}` must be an integer no less than {minimum}."
                        )
                    elif converter.max is not None and converter.min is not None:
                        message = _(
                            "Argument `{parameter_name}` must be an integer between {minimum} and {maximum}."
                        )
                elif converter.annotation is float:
                    if converter.min == 0 and converter.max is None:
                        message = _("Argument `{parameter_name}` must be a positive number.")
                    elif converter.min is None and converter.max is not None:
                        message = _(
                            "Argument `{parameter_name}` must be a number no more than {maximum}."
                        )
                    elif converter.min is not None and converter.max is None:
                        message = _(
                            "Argument `{parameter_name}` must be a number no less than {minimum}."
                        )
                    elif converter.max is not None and converter.min is not None:
                        message = _(
                            "Argument `{parameter_name}` must be a number between {minimum} and {maximum}."
                        )
                elif converter.annotation is str:
                    if error.minimum is None and error.maximum is not None:
                        message = _(
                            "Argument `{parameter_name}` must be a string with a length of no more than {maximum}."
                        )
                    elif error.minimum is not None and error.maximum is None:
                        message = _(
                            "Argument `{parameter_name}` must be a string with a length of no less than {minimum}."
                        )
                    elif error.maximum is not None and error.minimum is not None:
                        message = _(
                            "Argument `{parameter_name}` must be a string with a length of between {minimum} and {maximum}."
                        )
                await ctx.send(
                    message.format(
                        maximum=converter.max,
                        minimum=converter.min,
                        parameter_name=ctx.current_parameter.name,
                    )
                )
                return
            if isinstance(error.__cause__, ValueError):
                if converter is int:
                    await ctx.send(_('"{argument}" is not an integer.').format(argument=argument))
                    return
                if converter is float:
                    await ctx.send(_('"{argument}" is not a number.').format(argument=argument))
                    return
            if error.args:
                await ctx.send(error.args[0])
            else:
                await ctx.send_help()
        elif isinstance(error, commands.UserInputError):
            await ctx.send_help()
        elif isinstance(error, commands.DisabledCommand):
            disabled_message = await bot._config.disabled_command_msg()
            if disabled_message:
                disabled_message = disabled_message.replace("{command}", ctx.invoked_with)
                try:
                    await ctx.reply(disabled_message, mention_author=False)
                except discord.HTTPException:
                    await ctx.send(disabled_message)
        elif isinstance(error, commands.CommandInvokeError):
            log.exception(
                "Exception in command '{}'".format(ctx.command.qualified_name),
                exc_info=error.original,
            )
            exception_log = "Exception in command '{}'\n".format(ctx.command.qualified_name)
            exception_log += "".join(
                traceback.format_exception(type(error), error, error.__traceback__)
            )
            bot._last_exception = exception_log

            line = ("-" * 12) + ("-" * len(str(ctx.message.id)))
            description = code(
                (
                    f"[{type(error).__name__}]\n{line}\n"
                    f"[ID]      : {ctx.message.id}\n"
                    f"[Cog]     : {ctx.cog.qualified_name if ctx.cog else 'None'}\n"
                    f"[Command] : {ctx.command.qualified_name}\n"
                    f"[Type]    : {error.original.__class__.__name__}\n"
                    f"[Error]   : {error.original}\n"
                ),
                lang="prolog",
            )
            url = random.choice(
                [
                    "https://i.imgur.com/IZ512CN.gif",
                    "https://i.gifer.com/embedded/download/T8kd.gif",
                    "https://media.moddb.com/images/downloads/1/199/198436/MOSHED-2020-2-20-22-48-16.gif",
                ]
            )
            support_server = "https://discord.gg/ggQ7GcPm7P"
            embed = discord.Embed(color=discord.Color.red())
            embed.set_image(url=url)
            if await ctx.bot.is_owner(ctx.author):
                embed.title = "Master... Your command returned an error!"
                embed.description = description
                embed.set_footer(
                    text=f"Please use {ctx.prefix}tb for the detailed cause of this error."
                )
                view = None
            else:
                embed.title = "Uh Oh... An Error Occured!"
                embed.description = (
                    "It looks like an error has occurred. This has been reported to my owner.\n"
                    "You can consider joining [Starfire Support Server]({support_server}) , "
                    "my support server to receive assistance or provide context."
                ).format(support_server=support_server)
                embed.add_field(name="Error Details", value=description)
                embed.set_footer(
                    text=(
                        "Please refrain from using this command until this issue has been resolved.\n"
                        "Spamming errored commands will result in a blacklist."
                    )
                )
                view = discord.ui.View()
                server_invite = "https://discord.gg/ggQ7GcPm7P"
                if server_invite:
                    view.add_item(
                        discord.ui.Button(
                            style=discord.ButtonStyle.link,
                            label="Support Server",
                            url=server_invite,
                            emoji=ctx.bot.get_emoji(1005983057272115211),
                        )
                    )
            try:
                await ctx.send(embed=embed, reference=ctx.message, mention_author=False, view=view)
            except discord.HTTPException:
                await ctx.send(embed=embed, view=view)
        elif isinstance(error, commands.CommandNotFound):
            help_settings = await HelpSettings.from_context(ctx)
            fuzzy_commands = await fuzzy_command_search(
                ctx,
                commands=RedHelpFormatter.help_filter_func(
                    ctx, bot.walk_commands(), help_settings=help_settings
                ),
            )
            if not fuzzy_commands:
                pass
            elif await ctx.embed_requested():
                await ctx.send(embed=await format_fuzzy_results(ctx, fuzzy_commands, embed=True))
            else:
                await ctx.send(await format_fuzzy_results(ctx, fuzzy_commands, embed=False))
        elif isinstance(error, commands.BotMissingPermissions):
            embed = discord.Embed(title="I can't do that!", color=discord.Color.red())
            if bin(error.missing.value).count("1") == 1:  # Only missing a permission
                embed.description = _(
                    "I require the {permission} permission to run that command."
                ).format(permission=format_perms_list(error.missing))
            else:
                embed.description = _(
                    "I require {permission_list} permissions to run that command."
                ).format(permission_list=format_perms_list(error.missing))
            try:
                await ctx.reply(embed=embed, mention_author=False)
            except discord.HTTPException:
                await ctx.send(embed=embed)
        elif isinstance(error, commands.UserFeedbackCheckFailure):
            if error.message:
                await ctx.send(error.message)
        elif isinstance(error, commands.NoPrivateMessage):
            message = cross(_("That command is not available in DMs. Please try in a server!"))
            try:
                await ctx.reply(message, mention_author=False)
            except discord.HTTPException:
                await ctx.send(message)
        elif isinstance(error, commands.PrivateMessageOnly):
            message = cross(_("That command is only available in DMs. Please use it in my dms."))
            try:
                await ctx.reply(message, mention_author=False)
            except discord.HTTPException:
                await ctx.send(message)
        elif isinstance(error, commands.NSFWChannelRequired):
            m = cross(_("That command is only available in NSFW channels. Tsk tsk tsk."))
            try:
                await ctx.reply(m, mention_author=False)
            except discord.HTTPException:
                await ctx.send(m)
        elif isinstance(error, commands.CheckFailure):
            pass
        elif isinstance(error, commands.CommandOnCooldown):
            if ctx.bot._bypass_cooldowns and ctx.author.id in bot.owner_ids:
                ctx.command.reset_cooldown(ctx)
                new_ctx = await bot.get_context(ctx.message)
                await bot.invoke(new_ctx)
                return
            delay = discord.utils.format_dt(
                datetime.utcnow() + timedelta(seconds=error.retry_after), "R"
            )
            msg = _("This command is on cooldown. You must wait. \nTry again {delay}.").format(
                delay=delay
            )
            embed = discord.Embed(
                title=_("Command Cooldown"), description=msg, color=await ctx.embed_color()
            )
            try:
                await ctx.reply(embed=embed, delete_after=error.retry_after, mention_author=False)
            except discord.HTTPException:
                await ctx.send(embed=embed, delete_after=error.retry_after)
        elif isinstance(error, commands.MaxConcurrencyReached):
            if error.per is commands.BucketType.default:
                if error.number > 1:
                    msg = _(
                        "Too many people using this command.\n"
                        "It can only be used **__{number} times__** concurrently."
                    ).format(number=error.number)
                else:
                    msg = _(
                        "Too many people using this command.\n"
                        "It can only be used once concurrently."
                    )
            elif error.per in (commands.BucketType.user, commands.BucketType.member):
                if error.number > 1:
                    msg = _(
                        "That command is still completing.\n"
                        "It can only be used **__{number} times per {type}__** concurrently."
                    ).format(number=error.number, type=error.per.name)
                else:
                    msg = _(
                        "That command is still completing.\n"
                        "It can only be used **__once per {type}__** concurrently."
                    ).format(type=error.per.name)
            else:
                if error.number > 1:
                    msg = _(
                        "Too many people using this command.\n"
                        "It can only be used **__{number} times per {type}__** concurrently."
                    ).format(number=error.number, type=error.per.name)
                else:
                    msg = _(
                        "Too many people using this command.\n"
                        "It can only be used **__once per {type}__** concurrently."
                    ).format(type=error.per.name)
            mc_embed = discord.Embed(
                title="Max Concurrency Reached",
                description=msg,
                color=await ctx.embed_color(),
            )
            try:
                await ctx.reply(embed=mc_embed, mention_author=False)
            except discord.HTTPException:
                await ctx.send(embed=mc_embed)
        else:
            log.exception(type(error).__name__, exc_info=error)

    @bot.event
    async def on_message(message, /):
        await set_contextual_locales_from_guild(bot, message.guild)

        await bot.process_commands(message)
        discord_now = message.created_at
        if (
            not bot._checked_time_accuracy
            or (discord_now - timedelta(minutes=60)) > bot._checked_time_accuracy
        ):
            system_now = datetime.now(tz=timezone.utc)
            diff = abs((discord_now - system_now).total_seconds())
            if diff > 60:
                log.warning(
                    "Detected significant difference (%d seconds) in system clock to discord's "
                    "clock. Any time sensitive code may fail.",
                    diff,
                )
            bot._checked_time_accuracy = discord_now

    @bot.event
    async def on_command_add(command: commands.Command):
        if command.cog is not None:
            return

        await _disable_command_no_cog(command)

    async def _guild_added(guild: discord.Guild):
        disabled_commands = await bot._config.guild(guild).disabled_commands()
        for command_name in disabled_commands:
            command_obj = bot.get_command(command_name)
            if command_obj is not None:
                command_obj.disable_in(guild)

    @bot.event
    async def on_guild_join(guild: discord.Guild):
        await _guild_added(guild)

    @bot.event
    async def on_guild_available(guild: discord.Guild):
        # We need to check guild-disabled commands here since some cogs
        # are loaded prior to `on_ready`.
        await _guild_added(guild)

    @bot.event
    async def on_guild_remove(guild: discord.Guild):
        # Clean up any unneeded checks
        disabled_commands = await bot._config.guild(guild).disabled_commands()
        for command_name in disabled_commands:
            command_obj = bot.get_command(command_name)
            if command_obj is not None:
                command_obj.enable_in(guild)

    @bot.event
    async def on_cog_add(cog: commands.Cog):
        confs = get_latest_confs()
        for c in confs:
            uuid = c.unique_identifier
            group_data = c.custom_groups
            await bot._config.custom("CUSTOM_GROUPS", c.cog_name, uuid).set(group_data)

        await _disable_commands_cog(cog)

    async def _disable_command(
        command: commands.Command, global_disabled: list, guilds_data: dict
    ):
        if command.qualified_name in global_disabled:
            command.enabled = False
        for guild_id, data in guilds_data.items():
            guild_disabled_cmds = data.get("disabled_commands", [])
            if command.qualified_name in guild_disabled_cmds:
                command.disable_in(discord.Object(id=guild_id))

    async def _disable_commands_cog(cog: commands.Cog):
        global_disabled = await bot._config.disabled_commands()
        guilds_data = await bot._config.all_guilds()
        for command in cog.walk_commands():
            await _disable_command(command, global_disabled, guilds_data)

    async def _disable_command_no_cog(command: commands.Command):
        global_disabled = await bot._config.disabled_commands()
        guilds_data = await bot._config.all_guilds()
        await _disable_command(command, global_disabled, guilds_data)
