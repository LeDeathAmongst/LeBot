import calendar
import logging
import random
from collections import defaultdict, deque, namedtuple
from datetime import datetime, timezone, timedelta
from enum import Enum
from math import ceil
from typing import cast, Iterable, Literal

import discord
from redbot.core import Config, bank, commands, errors
from redbot.core.commands.converter import TimedeltaConverter, positive_int
from redbot.core.bot import Red
from redbot.core.i18n import Translator, cog_i18n
from redbot.core.utils import AsyncIter
from redbot.core.utils.chat_formatting import box, humanize_number
from redbot.core.utils.menus import menu

T_ = Translator("Economy", __file__)

logger = logging.getLogger("red.economy")

NUM_ENC = "\N{COMBINING ENCLOSING KEYCAP}"
VARIATION_SELECTOR = "\N{VARIATION SELECTOR-16}"
MOCK_MEMBER = namedtuple("Member", "id guild")

class SMReel(Enum):
    cherries = "\N{CHERRIES}"
    cookie = "\N{COOKIE}"
    two = "\N{DIGIT TWO}" + NUM_ENC
    flc = "\N{FOUR LEAF CLOVER}"
    cyclone = "\N{CYCLONE}"
    sunflower = "\N{SUNFLOWER}"
    six = "\N{DIGIT SIX}" + NUM_ENC
    mushroom = "\N{MUSHROOM}"
    heart = "\N{HEAVY BLACK HEART}" + VARIATION_SELECTOR
    snowflake = "\N{SNOWFLAKE}" + VARIATION_SELECTOR

_ = lambda s: s
PAYOUTS = {
    (SMReel.two, SMReel.two, SMReel.six): {
        "payout": lambda x: x * 50,
        "phrase": _("JACKPOT! 226! Your bid has been multiplied * 50!"),
    },
    (SMReel.flc, SMReel.flc, SMReel.flc): {
        "payout": lambda x: x * 25,
        "phrase": _("4LC! Your bid has been multiplied * 25!"),
    },
    (SMReel.cherries, SMReel.cherries, SMReel.cherries): {
        "payout": lambda x: x * 20,
        "phrase": _("Three cherries! Your bid has been multiplied * 20!"),
    },
    (SMReel.two, SMReel.six): {
        "payout": lambda x: x * 4,
        "phrase": _("2 6! Your bid has been multiplied * 4!"),
    },
    (SMReel.cherries, SMReel.cherries): {
        "payout": lambda x: x * 3,
        "phrase": _("Two cherries! Your bid has been multiplied * 3!"),
    },
    "3 symbols": {
        "payout": lambda x: x * 10,
        "phrase": _("Three symbols! Your bid has been multiplied * 10!"),
    },
    "2 symbols": {
        "payout": lambda x: x * 2,
        "phrase": _("Two consecutive symbols! Your bid has been multiplied * 2!"),
    },
}

SLOT_PAYOUTS_MSG = _(
    "Slot machine payouts:\n"
    "{two.value} {two.value} {six.value} Bet * 50\n"
    "{flc.value} {flc.value} {flc.value} Bet * 25\n"
    "{cherries.value} {cherries.value} {cherries.value} Bet * 20\n"
    "{two.value} {six.value} Bet * 4\n"
    "{cherries.value} {cherries.value} Bet * 3\n\n"
    "Three symbols: Bet * 10\n"
    "Two symbols: Bet * 2"
).format(**SMReel.__dict__)
_ = T_

def guild_only_check():
    async def pred(ctx: commands.Context):
        if await bank.is_global():
            return True
        elif ctx.guild is not None and not await bank.is_global():
            return True
        else:
            return False
    return commands.check(pred)

class SetParser:
    def __init__(self, argument):
        allowed = ("+", "-")
        try:
            self.sum = int(argument)
        except ValueError:
            raise commands.BadArgument(
                _("Invalid value, the argument must be an integer, optionally preceded with a `+` or `-` sign.")
            )
        if argument and argument[0] in allowed:
            if self.sum < 0:
                self.operation = "withdraw"
            elif self.sum > 0:
                self.operation = "deposit"
            else:
                raise commands.BadArgument(
                    _("Invalid value, the amount of currency to increase or decrease must be an integer different from zero.")
                )
            self.sum = abs(self.sum)
        else:
            self.operation = "set"

@cog_i18n(_)
class Economy(commands.Cog):
    """Get rich and have fun with imaginary currency!"""

    default_guild_settings = {
        "PAYDAY_TIME": 300,
        "PAYDAY_CREDITS": 120,
        "SLOT_MIN": 5,
        "SLOT_MAX": 100,
        "SLOT_TIME": 5,
        "REGISTER_CREDITS": 0,
    }

    default_global_settings = default_guild_settings
    default_member_settings = {"next_payday": 0, "last_slot": 0}
    default_role_settings = {"PAYDAY_CREDITS": 0}
    default_user_settings = default_member_settings

    def __init__(self, bot: Red):
        super().__init__()
        self.bot = bot
        self.config = Config.get_conf(self, 1256844281)
        self.config.register_guild(**self.default_guild_settings)
        self.config.register_global(**self.default_global_settings)
        self.config.register_member(**self.default_member_settings)
        self.config.register_user(**self.default_user_settings)
        self.config.register_role(**self.default_role_settings)
        self.slot_register = defaultdict(dict)

    async def red_delete_data_for_user(self, *, requester: Literal["discord_deleted_user", "owner", "user", "user_strict"], user_id: int):
        if requester != "discord_deleted_user":
            return
        await self.config.user_from_id(user_id).clear()
        all_members = await self.config.all_members()
        async for guild_id, guild_data in AsyncIter(all_members.items(), steps=100):
            if user_id in guild_data:
                await self.config.member_from_ids(guild_id, user_id).clear()

    @guild_only_check()
    @commands.group(name="bank")
    async def _bank(self, ctx: commands.Context):
        """Base command to manage the bank."""
        pass

    @_bank.command()
    async def balance(self, ctx: commands.Context, user: discord.Member = commands.Author):
        """Show the user's account balance."""
        bal = await bank.get_balance(user)
        currency = await bank.get_currency_name(ctx.guild)
        max_bal = await bank.get_max_balance(ctx.guild)
        if bal > max_bal:
            bal = max_bal
            await bank.set_balance(user, bal)
        embed = discord.Embed(title="Bank Balance", color=discord.Color.green())
        embed.add_field(name=user.display_name, value=f"{humanize_number(bal)} {currency}")
        await ctx.send(embed=embed)

    @_bank.command()
    async def transfer(self, ctx: commands.Context, to: discord.Member, amount: int):
        """Transfer currency to other users."""
        from_ = ctx.author
        currency = await bank.get_currency_name(ctx.guild)
        try:
            await bank.transfer_credits(from_, to, amount)
            embed = discord.Embed(title="Transfer Successful", color=discord.Color.green())
            embed.add_field(name="From", value=from_.display_name)
            embed.add_field(name="To", value=to.display_name)
            embed.add_field(name="Amount", value=f"{humanize_number(amount)} {currency}")
        except (ValueError, errors.BalanceTooHigh) as e:
            embed = discord.Embed(title="Transfer Failed", description=str(e), color=discord.Color.red())
        await ctx.send(embed=embed)

    @bank.is_owner_if_bank_global()
    @commands.admin_or_permissions(manage_guild=True)
    @_bank.command(name="set")
    async def _set(self, ctx: commands.Context, to: discord.Member, creds: SetParser):
        """Set the balance of a user's bank account."""
        author = ctx.author
        currency = await bank.get_currency_name(ctx.guild)
        try:
            if creds.operation == "deposit":
                await bank.deposit_credits(to, creds.sum)
                msg = _("{author} added {num} {currency} to {user}'s account.").format(
                    author=author.display_name,
                    num=humanize_number(creds.sum),
                    currency=currency,
                    user=to.display_name,
                )
            elif creds.operation == "withdraw":
                await bank.withdraw_credits(to, creds.sum)
                msg = _("{author} removed {num} {currency} from {user}'s account.").format(
                    author=author.display_name,
                    num=humanize_number(creds.sum),
                    currency=currency,
                    user=to.display_name,
                )
            else:
                await bank.set_balance(to, creds.sum)
                msg = _("{author} set {user}'s account balance to {num} {currency}.").format(
                    author=author.display_name,
                    num=humanize_number(creds.sum),
                    currency=currency,
                    user=to.display_name,
                )
            embed = discord.Embed(title="Account Modified", description=msg, color=discord.Color.green())
        except (ValueError, errors.BalanceTooHigh) as e:
            embed = discord.Embed(title="Error", description=str(e), color=discord.Color.red())
        await ctx.send(embed=embed)

    @guild_only_check()
    @commands.command()
    async def payday(self, ctx: commands.Context):
        """Get some free currency."""
        author = ctx.author
        guild = ctx.guild
        cur_time = calendar.timegm(ctx.message.created_at.utctimetuple())
        credits_name = await bank.get_currency_name(ctx.guild)
        if await bank.is_global():
            next_payday = await self.config.user(author).next_payday() + await self.config.PAYDAY_TIME()
            if cur_time >= next_payday:
                try:
                    await bank.deposit_credits(author, await self.config.PAYDAY_CREDITS())
                except errors.BalanceTooHigh as exc:
                    await bank.set_balance(author, exc.max_balance)
                    await ctx.send(
                        _("You've reached the maximum amount of {currency}! Please spend some more \N{GRIMACING FACE}\n\nYou currently have {new_balance} {currency}.").format(
                            currency=credits_name, new_balance=humanize_number(exc.max_balance)
                        )
                    )
                    return
                await self.config.user(author).next_payday.set(cur_time)
                pos = await bank.get_leaderboard_position(author)
                await ctx.send(
                    _("{author.mention} Here, take some {currency}. Enjoy! (+{amount} {currency}!)\n\nYou currently have {new_balance} {currency}.\n\nYou are currently #{pos} on the global leaderboard!").format(
                        author=author,
                        currency=credits_name,
                        amount=humanize_number(await self.config.PAYDAY_CREDITS()),
                        new_balance=humanize_number(await bank.get_balance(author)),
                        pos=humanize_number(pos) if pos else pos,
                    )
                )
            else:
                relative_time = discord.utils.format_dt(
                    datetime.now(timezone.utc) + timedelta(seconds=next_payday - cur_time), "R"
                )
                await ctx.send(
                    _("{author.mention} Too soon. Your next payday is {relative_time}.").format(
                        author=author, relative_time=relative_time
                    )
                )
        else:
            next_payday = (
                await self.config.member(author).next_payday()
                + await self.config.guild(guild).PAYDAY_TIME()
            )
            if cur_time >= next_payday:
                credit_amount = await self.config.guild(guild).PAYDAY_CREDITS()
                for role in author.roles:
                    role_credits = await self.config.role(role).PAYDAY_CREDITS()
                    if role_credits > credit_amount:
                        credit_amount = role_credits
                try:
                    await bank.deposit_credits(author, credit_amount)
                except errors.BalanceTooHigh as exc:
                    await bank.set_balance(author, exc.max_balance)
                    await ctx.send(
                        _("You've reached the maximum amount of {currency}! Please spend some more \N{GRIMACING FACE}\n\nYou currently have {new_balance} {currency}.").format(
                            currency=credits_name, new_balance=humanize_number(exc.max_balance)
                        )
                    )
                    return
                next_payday = cur_time
                await self.config.member(author).next_payday.set(next_payday)
                pos = await bank.get_leaderboard_position(author)
                await ctx.send(
                    _("{author.mention} Here, take some {currency}. Enjoy! (+{amount} {currency}!)\n\nYou currently have {new_balance} {currency}.\n\nYou are currently #{pos} on the global leaderboard!").format(
                        author=author,
                        currency=credits_name,
                        amount=humanize_number(credit_amount),
                        new_balance=humanize_number(await bank.get_balance(author)),
                        pos=humanize_number(pos) if pos else pos,
                    )
                )
            else:
                relative_time = discord.utils.format_dt(
                    datetime.now(timezone.utc) + timedelta(seconds=next_payday - cur_time), "R"
                )
                await ctx.send(
                    _("{author.mention} Too soon. Your next payday is {relative_time}.").format(
                        author=author, relative_time=relative_time
                    )
                )

    @commands.command()
    @guild_only_check()
    async def leaderboard(self, ctx: commands.Context, top: int = 10, show_global: bool = False):
        """Print the leaderboard."""
        guild = ctx.guild
        author = ctx.author
        embed_requested = await ctx.embed_requested()
        footer_message = _("Page {page_num}/{page_len}.")
        max_bal = await bank.get_max_balance(ctx.guild)

        if top < 1:
            top = 10

        base_embed = discord.Embed(title=_("Economy Leaderboard"), color=discord.Color.gold())
        if show_global and await bank.is_global():
            bank_sorted = await bank.get_leaderboard(positions=top, guild=None)
            base_embed.set_author(name=ctx.bot.user.display_name, icon_url=ctx.bot.user.display_avatar)
        else:
            bank_sorted = await bank.get_leaderboard(positions=top, guild=guild)
            if guild:
                base_embed.set_author(name=guild.name, icon_url=guild.icon)

        try:
            bal_len = len(humanize_number(bank_sorted[0][1]["balance"]))
            bal_len_max = len(humanize_number(max_bal))
            if bal_len > bal_len_max:
                bal_len = bal_len_max
        except IndexError:
            embed = discord.Embed(title=_("Economy Leaderboard"), description=_("There are no accounts in the bank."), color=discord.Color.red())
            return await ctx.send(embed=embed)

        pound_len = len(str(len(bank_sorted)))
        header = "{pound:{pound_len}}{score:{bal_len}}{name:2}\n".format(
            pound="#", name=_("Name"), score=_("Score"), bal_len=bal_len + 6, pound_len=pound_len + 3
        )
        highscores = []
        pos = 1
        temp_msg = header
        for acc in bank_sorted:
            try:
                name = guild.get_member(acc[0]).display_name
            except AttributeError:
                user_id = ""
                if await ctx.bot.is_owner(ctx.author):
                    user_id = f"({str(acc[0])})"
                name = f"{acc[1]['name']} {user_id}"

            balance = acc[1]["balance"]
            if balance > max_bal:
                balance = max_bal
                await bank.set_balance(MOCK_MEMBER(acc[0], guild), balance)
            balance = humanize_number(balance)
            if acc[0] != author.id:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{balance: <{bal_len + 5}} {name}\n"
                )
            else:
                temp_msg += (
                    f"{f'{humanize_number(pos)}.': <{pound_len+2}} "
                    f"{balance: <{bal_len + 5}} "
                    f"<<{author.display_name}>>\n"
                )
            if pos % 10 == 0:
                if embed_requested:
                    embed = base_embed.copy()
                    embed.description = box(temp_msg, lang="md")
                    embed.set_footer(
                        text=footer_message.format(
                            page_num=len(highscores) + 1,
                            page_len=ceil(len(bank_sorted) / 10),
                        )
                    )
                    highscores.append(embed)
                else:
                    highscores.append(box(temp_msg, lang="md"))
                temp_msg = header
            pos += 1

        if temp_msg != header:
            if embed_requested:
                embed = base_embed.copy()
                embed.description = box(temp_msg, lang="md")
                embed.set_footer(
                    text=footer_message.format(
                        page_num=len(highscores) + 1,
                        page_len=ceil(len(bank_sorted) / 10),
                    )
                )
                highscores.append(embed)
            else:
                highscores.append(box(temp_msg, lang="md"))

        if highscores:
            await menu(ctx, highscores)
        else:
            await ctx.send(_("No balances found."))

    @commands.command()
    @guild_only_check()
    async def payouts(self, ctx: commands.Context):
        """Show the payouts for the slot machine."""
        try:
            await ctx.author.send(SLOT_PAYOUTS_MSG)
        except discord.Forbidden:
            await ctx.send(_("I can't send direct messages to you."))

    @commands.command()
    @guild_only_check()
    async def slot(self, ctx: commands.Context, bid: int):
        """Use the slot machine."""
        author = ctx.author
        guild = ctx.guild
        channel = ctx.channel
        if await bank.is_global():
            valid_bid = await self.config.SLOT_MIN() <= bid <= await self.config.SLOT_MAX()
            slot_time = await self.config.SLOT_TIME()
            last_slot = await self.config.user(author).last_slot()
        else:
            valid_bid = (
                await self.config.guild(guild).SLOT_MIN()
                <= bid
                <= await self.config.guild(guild).SLOT_MAX()
            )
            slot_time = await self.config.guild(guild).SLOT_TIME()
            last_slot = await self.config.member(author).last_slot()
        now = calendar.timegm(ctx.message.created_at.utctimetuple())

        if (now - last_slot) < slot_time:
            await ctx.send(_("You're on cooldown, try again in a bit."))
            return
        if not valid_bid:
            await ctx.send(_("That's an invalid bid amount, sorry :/"))
            return
        if not await bank.can_spend(author, bid):
            await ctx.send(_("You ain't got enough money, friend."))
            return
        if await bank.is_global():
            await self.config.user(author).last_slot.set(now)
        else:
            await self.config.member(author).last_slot.set(now)
        await self.slot_machine(author, channel, bid)

    @staticmethod
    async def slot_machine(author, channel, bid):
        default_reel = deque(cast(Iterable, SMReel))
        reels = []
        for i in range(3):
            default_reel.rotate(random.randint(-999, 999))  # weeeeee
            new_reel = deque(default_reel, maxlen=3)  # we need only 3 symbols
            reels.append(new_reel)  # for each reel
        rows = (
            (reels[0][0], reels[1][0], reels[2][0]),
            (reels[0][1], reels[1][1], reels[2][1]),
            (reels[0][2], reels[1][2], reels[2][2]),
        )

        slot = "~~\n~~"  # Mobile friendly
        for i, row in enumerate(rows):  # Let's build the slot to show
            sign = "  "
            if i == 1:
                sign = ">"
            slot += "{}{} {} {}\n".format(
                sign, *[c.value for c in row]  # pylint: disable=no-member
            )

        payout = PAYOUTS.get(rows[1])
        if not payout:
            # Checks for two-consecutive-symbols special rewards
            payout = PAYOUTS.get((rows[1][0], rows[1][1]), PAYOUTS.get((rows[1][1], rows[1][2])))
        if not payout:
            # Still nothing. Let's check for 3 generic same symbols
            # or 2 consecutive symbols
            has_three = rows[1][0] == rows[1][1] == rows[1][2]
            has_two = (rows[1][0] == rows[1][1]) or (rows[1][1] == rows[1][2])
            if has_three:
                payout = PAYOUTS["3 symbols"]
            elif has_two:
                payout = PAYOUTS["2 symbols"]

        if payout:
            then = await bank.get_balance(author)
            pay = payout["payout"](bid)
            now = then - bid + pay
            try:
                await bank.set_balance(author, now)
            except errors.BalanceTooHigh as exc:
                await bank.set_balance(author, exc.max_balance)
                await channel.send(
                    _(
                        "You've reached the maximum amount of {currency}! "
                        "Please spend some more \N{GRIMACING FACE}\n{old_balance} -> {new_balance}!"
                    ).format(
                        currency=await bank.get_currency_name(getattr(channel, "guild", None)),
                        old_balance=humanize_number(then),
                        new_balance=humanize_number(exc.max_balance),
                    )
                )
                return
            phrase = T_(payout["phrase"])
        else:
            then = await bank.get_balance(author)
            await bank.withdraw_credits(author, bid)
            now = then - bid
            phrase = _("Nothing!")
        await channel.send(
            (
                "{slot}\n{author.mention} {phrase}\n\n"
                + _("Your bid: {bid}")
                + _("\n{old_balance} - {bid} (Your bid) + {pay} (Winnings) = {new_balance}!")
            ).format(
                slot=slot,
                author=author,
                phrase=phrase,
                bid=humanize_number(bid),
                old_balance=humanize_number(then),
                new_balance=humanize_number(now),
                pay=humanize_number(pay),
            )
        )

    @guild_only_check()
    @bank.is_owner_if_bank_global()
    @commands.admin_or_permissions(manage_guild=True)
    @commands.group()
    async def economyset(self, ctx: commands.Context):
        """Base command to manage Economy settings."""

    @economyset.command(name="showsettings")
    async def economyset_showsettings(self, ctx: commands.Context):
        """Shows the current economy settings"""
        role_paydays = []
        guild = ctx.guild
        if await bank.is_global():
            conf = self.config
        else:
            conf = self.config.guild(guild)
            for role in guild.roles:
                rolepayday = await self.config.role(role).PAYDAY_CREDITS()
                if rolepayday:
                    role_paydays.append(f"{role}: {rolepayday}")
        embed = discord.Embed(title="Economy Settings", color=discord.Color.blue())
        embed.add_field(name="Minimum slot bid", value=humanize_number(await conf.SLOT_MIN()))
        embed.add_field(name="Maximum slot bid", value=humanize_number(await conf.SLOT_MAX()))
        embed.add_field(name="Slot cooldown", value=humanize_number(await conf.SLOT_TIME()))
        embed.add_field(name="Payday amount", value=humanize_number(await conf.PAYDAY_CREDITS()))
        embed.add_field(name="Payday cooldown", value=humanize_number(await conf.PAYDAY_TIME()))
        await ctx.send(embed=embed)
        if role_paydays:
            embed = discord.Embed(title="Role Payday Amounts", color=discord.Color.blue())
            for role_payday in role_paydays:
                role, amount = role_payday.split(': ')
                embed.add_field(name=role, value=amount)
            await ctx.send(embed=embed)

    @economyset.command()
    async def slotmin(self, ctx: commands.Context, bid: positive_int):
        """Set the minimum slot machine bid."""
        guild = ctx.guild
        is_global = await bank.is_global()
        if is_global:
            slot_max = await self.config.SLOT_MAX()
        else:
            slot_max = await self.config.guild(guild).SLOT_MAX()
        if bid > slot_max:
            await ctx.send(
                _("Warning: Minimum bid is greater than the maximum bid ({max_bid}). Slots will not work.").format(max_bid=humanize_number(slot_max))
            )
        if is_global:
            await self.config.SLOT_MIN.set(bid)
        else:
            await self.config.guild(guild).SLOT_MIN.set(bid)
        credits_name = await bank.get_currency_name(guild)
        embed = discord.Embed(title="Slot Machine Minimum Bid", color=discord.Color.green())
        embed.description = _("Minimum bid is now {bid} {currency}.").format(
            bid=humanize_number(bid), currency=credits_name
        )
        await ctx.send(embed=embed)

    @economyset.command()
    async def slotmax(self, ctx: commands.Context, bid: positive_int):
        """Set the maximum slot machine bid."""
        guild = ctx.guild
        is_global = await bank.is_global()
        if is_global:
            slot_min = await self.config.SLOT_MIN()
        else:
            slot_min = await self.config.guild(guild).SLOT_MIN()
        if bid < slot_min:
            await ctx.send(
                _("Warning: Maximum bid is less than the minimum bid ({min_bid}). Slots will not work.").format(min_bid=humanize_number(slot_min))
            )
        credits_name = await bank.get_currency_name(guild)
        if is_global:
            await self.config.SLOT_MAX.set(bid)
        else:
            await self.config.guild(guild).SLOT_MAX.set(bid)
        embed = discord.Embed(title="Slot Machine Maximum Bid", color=discord.Color.green())
        embed.description = _("Maximum bid is now {bid} {currency}.").format(
            bid=humanize_number(bid), currency=credits_name
        )
        await ctx.send(embed=embed)

    @economyset.command()
    async def slottime(self, ctx: commands.Context, *, duration: TimedeltaConverter(default_unit="seconds")):
        """Set the cooldown for the slot machine."""
        seconds = int(duration.total_seconds())
        guild = ctx.guild
        if await bank.is_global():
            await self.config.SLOT_TIME.set(seconds)
        else:
            await self.config.guild(guild).SLOT_TIME.set(seconds)
        embed = discord.Embed(title="Slot Machine Cooldown", color=discord.Color.green())
        embed.description = _("Cooldown is now {num} seconds.").format(num=seconds)
        await ctx.send(embed=embed)

    @economyset.command()
    async def paydaytime(self, ctx: commands.Context, *, duration: TimedeltaConverter(default_unit="seconds")):
        """Set the cooldown for the payday command."""
        seconds = int(duration.total_seconds())
        guild = ctx.guild
        if await bank.is_global():
            await self.config.PAYDAY_TIME.set(seconds)
        else:
            await self.config.guild(guild).PAYDAY_TIME.set(seconds)
        embed = discord.Embed(title="Payday Cooldown", color=discord.Color.green())
        embed.description = _("Value modified. At least {num} seconds must pass between each payday.").format(num=seconds)
        await ctx.send(embed=embed)

    @economyset.command()
    async def paydayamount(self, ctx: commands.Context, creds: int):
        """Set the amount earned each payday."""
        guild = ctx.guild
        max_balance = await bank.get_max_balance(ctx.guild)
        if creds <= 0 or creds > max_balance:
            embed = discord.Embed(title="Error", color=discord.Color.red())
            embed.description = _("Amount must be greater than zero and less than {maxbal}.").format(maxbal=humanize_number(max_balance))
            return await ctx.send(embed=embed)

        credits_name = await bank.get_currency_name(guild)
        if await bank.is_global():
            await self.config.PAYDAY_CREDITS.set(creds)
        else:
            await self.config.guild(guild).PAYDAY_CREDITS.set(creds)
        embed = discord.Embed(title="Payday Amount Set", color=discord.Color.green())
        embed.description = _("Every payday will now give {num} {currency}.").format(
            num=humanize_number(creds), currency=credits_name
        )
        await ctx.send(embed=embed)

    @economyset.command()
    async def rolepaydayamount(self, ctx: commands.Context, role: discord.Role, creds: int):
        """Set the amount earned each payday for a role."""
        guild = ctx.guild
        max_balance = await bank.get_max_balance(ctx.guild)
        if creds >= max_balance:
            embed = discord.Embed(title="Error", color=discord.Color.red())
            embed.description = _(
                "The bank requires that you set the payday to be less than"
                " its maximum balance of {maxbal}."
            ).format(maxbal=humanize_number(max_balance))
            return await ctx.send(embed=embed)
        credits_name = await bank.get_currency_name(guild)
        if await bank.is_global():
            embed = discord.Embed(title="Error", color=discord.Color.red())
            embed.description = _("The bank must be per-server for per-role paydays to work.")
            await ctx.send(embed=embed)
        else:
            if creds <= 0:
                default_creds = await self.config.guild(guild).PAYDAY_CREDITS()
                await self.config.role(role).clear()
                embed = discord.Embed(title="Role Payday Removed", color=discord.Color.green())
                embed.description = _(
                    "The payday value attached to role has been removed. "
                    "Users with this role will now receive the default pay "
                    "of {num} {currency}."
                ).format(num=humanize_number(default_creds), currency=credits_name)
            else:
                await self.config.role(role).PAYDAY_CREDITS.set(creds)
                embed = discord.Embed(title="Role Payday Set", color=discord.Color.green())
                embed.description = _(
                    "Every payday will now give {num} {currency} "
                    "to people with the role {role_name}."
                ).format(
                    num=humanize_number(creds), currency=credits_name, role_name=role.name
                )
            await ctx.send(embed=embed)
