from __future__ import annotations

import logging

import discord
from typing import Any, List, Dict, Optional, TYPE_CHECKING, Union
from redbot.core import commands
from redbot.core.commands import get_dict_converter
from redbot.core.i18n import Translator
from redbot.vendored.discord.ext import menus

if TYPE_CHECKING:
    from redbot.core.bot import Red

log = logging.getLogger("red.core.utils.views")

__all__ = (
    "SimpleMenu",
    "SetApiModal",
    "SetApiView",
    "ContactDmReplyModal",
    "ContactDmView",
    "InviteView",
    "View",
    "ConfirmView",
)

_ = Translator("UtilsViews", __file__)

_ACCEPTABLE_PAGE_TYPES = Union[Dict[str, Union[str, discord.Embed]], discord.Embed, str]


class _SimplePageSource(menus.ListPageSource):
    def __init__(self, items: List[_ACCEPTABLE_PAGE_TYPES]):
        super().__init__(items, per_page=1)

    async def format_page(
        self, view: discord.ui.View, page: _ACCEPTABLE_PAGE_TYPES
    ) -> Union[str, discord.Embed]:
        return page


class _SelectMenu(discord.ui.Select):
    def __init__(self, options: List[discord.SelectOption]):
        super().__init__(
            placeholder=_("Select a Page"), min_values=1, max_values=1, options=options
        )

    async def callback(self, interaction: discord.Interaction):
        index = int(self.values[0])
        self.view.current_page = index
        kwargs = await self.view.get_page(self.view.current_page)
        if kwargs.get("files") or kwargs.get("file"):
            kwargs["attachments"] = list(kwargs.pop("files") or kwargs.pop("file"))
        await interaction.response.edit_message(**kwargs)


class _NavigateButton(discord.ui.Button):
    def __init__(
        self, style: discord.ButtonStyle, emoji: Union[str, discord.PartialEmoji], direction: int
    ):
        super().__init__(style=style, emoji=emoji)
        self.direction = direction

    async def callback(self, interaction: discord.Interaction):
        if self.direction == 0:
            self.view.current_page = 0
        elif self.direction == self.view.source.get_max_pages():
            self.view.current_page = self.view.source.get_max_pages() - 1
        else:
            self.view.current_page += self.direction
        kwargs = await self.view.get_page(self.view.current_page)
        if kwargs.get("files") or kwargs.get("file"):
            kwargs["attachments"] = list(kwargs.pop("files") or kwargs.pop("file"))
        await interaction.response.edit_message(**kwargs)


class _StopButton(discord.ui.Button):
    def __init__(
        self,
        style: discord.ButtonStyle = discord.ButtonStyle.red,
        emoji: Union[str, discord.PartialEmoji] = "✖️",
        row: Optional[int] = None,
    ):
        super().__init__(style=style, emoji=emoji, row=row)

    async def callback(self, interaction: discord.Interaction):
        self.view.stop()
        if interaction.message.flags.ephemeral:
            await interaction.response.edit_message(view=None)
            return
        await interaction.message.delete()


class SimpleMenu(discord.ui.View):
    """
    A simple Button Menu.

    Parameters
    ----------
    pages: `list` of `str`, `discord.Embed`, or `dict`.
        The pages of the menu.
        if the page is a `dict` its keys must be valid messageable args.
        e,g. "content", "embed", etc.
    page_start: int
        The page to start the menu at.
    timeout: float
        The time (in seconds) to wait for a reaction
        defaults to 180 seconds.
    delete_after_timeout: bool
        Whether or not to delete the message after
        the timeout has expired.
        Defaults to False.
    disable_after_timeout: bool
        Whether to disable all components on the
        menu after timeout has expired. By default
        the view is removed from the message on timeout.
        Defaults to False.
    use_select_menu: bool
        Whether or not to include a select menu
        to jump specifically between pages.
        Defaults to False.
    use_select_only: bool
        Whether the menu will only display the select
        menu for paginating instead of the buttons.
        The stop button will remain but is positioned
        under the select menu in this instance.
        Defaults to False.

    Examples
    --------
        You can provide a list of strings::

            from redbot.core.utils.views import SimpleMenu
            pages = ["Hello", "Hi", "Bonjour", "Salut"]
            await SimpleMenu(pages).start(ctx)

        You can provide a list of dicts::

            from redbot.core.utils.views import SimpleMenu
            pages = [{"content": "My content", "embed": discord.Embed(description="hello")}]
            await SimpleMenu(pages).start(ctx)
    """

    def __init__(
        self,
        pages: List[_ACCEPTABLE_PAGE_TYPES],
        timeout: float = 180.0,
        page_start: int = 0,
        delete_after_timeout: bool = False,
        disable_after_timeout: bool = True,
        use_select_menu: bool = False,
        use_select_only: bool = False,
    ) -> None:
        super().__init__(timeout=timeout)
        self._fallback_author_to_ctx = True
        self.author: Optional[discord.abc.User] = None
        self.message: Optional[discord.Message] = None
        self._source = _SimplePageSource(items=pages)
        self.ctx: Optional[commands.Context] = None
        self.current_page = page_start
        self.delete_after_timeout = delete_after_timeout
        self.disable_after_timeout = disable_after_timeout
        self.use_select_menu = use_select_menu or use_select_only
        self.use_select_only = use_select_only

        self.stop_button = _StopButton(
            discord.ButtonStyle.red,
            discord.PartialEmoji(name="Cross", animated=True, id=984377347958538262),
        )
        self.first_button = _NavigateButton(
            discord.ButtonStyle.gray,
            discord.PartialEmoji(name="First", animated=True, id=984377537855623178),
            direction=0,
        )
        self.backward_button = _NavigateButton(
            discord.ButtonStyle.gray,
            discord.PartialEmoji(name="Left", animated=True, id=984377515999109190),
            direction=-1,
        )
        self.forward_button = _NavigateButton(
            discord.ButtonStyle.gray,
            discord.PartialEmoji(name="Right", animated=True, id=984377456301596692),
            direction=1,
        )
        self.last_button = _NavigateButton(
            discord.ButtonStyle.gray,
            discord.PartialEmoji(name="Last", animated=True, id=984377411749707796),
            direction=self.source.get_max_pages(),
        )
        self.select_options = [
            discord.SelectOption(label=_("Page {num}").format(num=num + 1), value=num)
            for num, x in enumerate(pages)
        ]
        self.select_menu = self._get_select_menu()
        if self.use_select_menu and self.source.is_paginating():
            self.add_item(self.select_menu)
        self.add_item(self.stop_button)
        if self.source.is_paginating() and not self.use_select_only:
            self.remove_item(self.stop_button)
            self.add_item(self.first_button)
            self.add_item(self.backward_button)
            self.add_item(self.stop_button)
            self.add_item(self.forward_button)
            self.add_item(self.last_button)
            if len(pages) < 3:
                self.remove_item(self.first_button)
                self.remove_item(self.last_button)

    @property
    def source(self):
        return self._source

    @property
    def author(self) -> Optional[discord.abc.User]:
        if self._author is not None:
            return self._author
        if self._fallback_author_to_ctx:
            return getattr(self.ctx, "author", None)
        return None

    @author.setter
    def author(self, value: Optional[discord.abc.User]) -> None:
        self._fallback_author_to_ctx = False
        self._author = value

    async def on_timeout(self):
        try:
            if self.delete_after_timeout and not self.message.flags.ephemeral:
                await self.message.delete()
            elif self.disable_after_timeout:
                for child in self.children:
                    child.disabled = True
                await self.message.edit(view=self)
            else:
                await self.message.edit(view=None)
        except discord.HTTPException:
            # message could no longer be there or we may not be able to edit/delete it anymore
            pass

    def _get_select_menu(self):
        # handles modifying the select menu if more than 25 pages are provided
        # this will show the previous 12 and next 13 pages in the select menu
        # based on the currently displayed page. Once you reach close to the max
        # pages it will display the last 25 pages.
        if len(self.select_options) > 25:
            minus_diff = None
            plus_diff = 25
            if 12 < self.current_page < len(self.select_options) - 25:
                minus_diff = self.current_page - 12
                plus_diff = self.current_page + 13
            elif self.current_page >= len(self.select_options) - 25:
                minus_diff = len(self.select_options) - 25
                plus_diff = None
            options = self.select_options[minus_diff:plus_diff]
        else:
            options = self.select_options[:25]
        return _SelectMenu(options)

    async def start(
        self,
        ctx: commands.Context,
        *,
        user: Optional[discord.abc.User] = None,
        ephemeral: bool = False,
    ):
        """
        Used to start the menu displaying the first page requested.

        .. warning::
            The ``user`` parameter is considered `provisional <developer-guarantees-exclusions>`.
            If no issues arise, we plan on including it under developer guarantees
            in the first release made after 2024-05-24.

        Parameters
        ----------
            ctx: `commands.Context`
                The context to start the menu in.
            user: discord.User
                The user allowed to interact with the menu.
                If this is ``None``, ``ctx.author`` will be able to interact with the menu.
                .. warning::
                    This parameter is `provisional <developer-guarantees-exclusions>`.
                    If no issues arise, we plan on including it under developer guarantees
                    in the first release made after 2024-05-24.
            ephemeral: `bool`
                Send the message ephemerally. This only works
                if the context is from a slash command interaction.
        """
        self._fallback_author_to_ctx = True
        if user is not None:
            self.author = user
        self.ctx = ctx
        kwargs = await self.get_page(self.current_page)
        self.message = await ctx.send(**kwargs, ephemeral=ephemeral)

    async def start_dm(self, user: discord.User):
        """
        Used to start displaying the menu in a direct message.
        Parameters
        ----------
            user: `discord.User`
                The user that will be direct messaged by the bot.
        """
        self.author = user
        kwargs = await self.get_page(self.current_page)
        self.message = await user.send(**kwargs)

    async def get_page(self, page_num: int) -> Dict[str, Optional[Any]]:
        try:
            page = await self.source.get_page(page_num)
        except IndexError:
            self.current_page = 0
            page = await self.source.get_page(self.current_page)
        value = await self.source.format_page(self, page)
        if self.use_select_menu and len(self.select_options) > 25 and self.source.is_paginating():
            self.remove_item(self.select_menu)
            self.select_menu = self._get_select_menu()
            self.add_item(self.select_menu)
        ret: Dict[str, Optional[Any]] = {"view": self}
        if isinstance(value, dict):
            ret.update(value)
        elif isinstance(value, str):
            ret.update({"content": value, "embed": None})
        elif isinstance(value, discord.Embed):
            ret.update({"embed": value, "content": None})
        return ret

    async def interaction_check(self, interaction: discord.Interaction):
        """Ensure only the author is allowed to interact with the menu."""
        allowed_ids = (getattr(self.author, "id", None),)
        if interaction.user.id not in allowed_ids:
            await interaction.response.send_message(
                content=_("You are not authorized to interact with this menu."), ephemeral=True
            )
            return False
        return True


class SetApiModal(discord.ui.Modal):
    """
    A secure ``discord.ui.Modal`` used to set API keys.

    This Modal can either be used standalone with its own ``discord.ui.View``
    for custom implementations, or created via ``SetApiView``
    to have an easy to implemement secure way of setting API keys.

    Parameters
    ----------
    default_service: Optional[str]
        The service to add the API keys to.
        If this is omitted the bot owner is allowed to set his own service.
        Defaults to ``None``.
    default_keys: Optional[Dict[str, str]]
        The API keys the service is expecting.
        This will only allow the bot owner to set keys the Modal is expecting.
        Defaults to ``None``.
    """

    def __init__(
        self,
        default_service: Optional[str] = None,
        default_keys: Optional[Dict[str, str]] = None,
    ):
        self.default_service = default_service
        self.default_keys: List[str] = []
        if default_keys is not None:
            self.default_keys = list(default_keys.keys())
        self.default_keys_fmt = self._format_keys(default_keys)

        _placeholder_token = "client_id YOUR_CLIENT_ID\nclient_secret YOUR_CLIENT_SECRET"
        _placeholder_service = "service"
        if self.default_service is not None:
            _placeholder_service = self.default_service

        self.title = "Set API Key"
        self.keys_label = "Keys and tokens"
        if self.default_service is not None:
            self.title = "Set API Keys for {service}".format(service=self.default_service)
            self.keys_label = "Keys and tokens for {service}".format(service=self.default_service)
            self.default_service = self.default_service.lower()
            # Lower here to prevent someone from capitalizing a service name for the sake of UX.

        super().__init__(title=self.title)

        self.service_input = discord.ui.TextInput(
            label="Service",
            required=True,
            placeholder=_placeholder_service,
            default=self.default_service,
        )

        self.token_input = discord.ui.TextInput(
            label=self.keys_label,
            style=discord.TextStyle.long,
            required=True,
            placeholder=_placeholder_token,
            default=self.default_keys_fmt,
        )

        if self.default_service is None:
            self.add_item(self.service_input)
        self.add_item(self.token_input)

    @staticmethod
    def _format_keys(keys: Optional[Dict[str, str]]) -> Optional[str]:
        """Format the keys to be used on a long discord.TextInput format"""
        if keys is not None:
            ret = ""
            for k, v in keys.items():
                if v:
                    ret += f"{k} {v}\n"
                else:
                    ret += f"{k} YOUR_{k.upper()}\n"
            return ret
        else:
            return None

    async def on_submit(self, interaction: discord.Interaction):
        if not await interaction.client.is_owner(
            interaction.user
        ):  # Prevent non-bot owners from somehow acquiring and saving the modal.
            return await interaction.response.send_message(
                "This modal is for bot owners only. Whoops!", ephemeral=True
            )

        if self.default_keys is not None:
            converter = get_dict_converter(*self.default_keys, delims=[";", ",", " "])
        else:
            converter = get_dict_converter(delims=[";", ",", " "])
        tokens = " ".join(self.token_input.value.split("\n")).rstrip()

        try:
            tokens = await converter().convert(None, tokens)
        except commands.BadArgument as exc:
            return await interaction.response.send_message(
                "{error_message}\nPlease try again.".format(error_message=str(exc)),
                ephemeral=True,
            )

        if self.default_service is not None:  # Check is there is a service set.
            await interaction.client.set_shared_api_tokens(self.default_service, **tokens)
            return await interaction.response.send_message(
                "`{service}` API tokens have been set.".format(service=self.default_service),
                ephemeral=True,
            )
        else:
            service = self.service_input.value.lower()
            await interaction.client.set_shared_api_tokens(service, **tokens)
            return await interaction.response.send_message(
                "`{service}` API tokens have been set.".format(service=service),
                ephemeral=True,
            )


class SetApiView(discord.ui.View):
    """
    A secure ``discord.ui.View`` used to set API keys.

    This view is an standalone, easy to implement ``discord.ui.View``
    to allow an bot owner to securely set API keys in a public environment.

    Parameters
    ----------
    default_service: Optional[str]
        The service to add the API keys to.
        If this is omitted the bot owner is allowed to set his own service.
        Defaults to ``None``.
    default_keys: Optional[Dict[str, str]]
        The API keys the service is expecting.
        This will only allow the bot owner to set keys the Modal is expecting.
        Defaults to ``None``.
    """

    def __init__(
        self,
        default_service: Optional[str] = None,
        default_keys: Optional[Dict[str, str]] = None,
    ):
        super().__init__()
        self.default_service = default_service
        self.default_keys = default_keys

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not await interaction.client.is_owner(interaction.user):
            await interaction.response.send_message(
                _("This button is for bot owners only, oh well."), ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Set API Token", style=discord.ButtonStyle.gray)
    async def auth_button(self, interaction: discord.Interaction, button: discord.Button):
        return await interaction.response.send_modal(
            SetApiModal(self.default_service, self.default_keys)
        )


class ConfirmView(discord.ui.View):
    """
    A simple `discord.ui.View` used for confirming something.

    Parameters
    ----------
    author: Optional[discord.abc.User]
        The user who you want to be interacting with the confirmation.
        If this is omitted anyone can click yes or no.
    timeout: float
        The timeout of the view in seconds. Defaults to ``180`` seconds.
    disable_buttons: bool
        Whether to disable the buttons instead of removing them from the message after the timeout.
        Defaults to ``False``.

    Examples
    --------
    Using the view::

        view = ConfirmView(ctx.author)
        # attach the message to the view after sending it.
        # This way, the view will be automatically removed
        # from the message after the timeout.
        view.message = await ctx.send("Are you sure you about that?", view=view)
        await view.wait()
        if view.result:
            await ctx.send("Okay I will do that.")
        else:
            await ctx.send("I will not be doing that then.")

    Auto-disable the buttons after timeout if nothing is pressed::

        view = ConfirmView(ctx.author, disable_buttons=True)
        view.message = await ctx.send("Are you sure you about that?", view=view)
        await view.wait()
        if view.result:
            await ctx.send("Okay I will do that.")
        else:
            await ctx.send("I will not be doing that then.")

    Attributes
    ----------
    result: Optional[bool]
        The result of the confirm view.
    author: Optional[discord.abc.User]
        The author of the message who is allowed to press the buttons.
    message: Optional[discord.Message]
        The message the confirm view is sent on. This can be set while
        sending the message. This can also be left as ``None`` in which case
        nothing will happen in `on_timeout()`, if the view is never interacted with.
    disable_buttons: bool
        Whether to disable the buttons isntead of removing them on timeout
        (if the `message` attribute has been set on the view).
    """

    def __init__(
        self,
        author: Optional[discord.abc.User] = None,
        *,
        timeout: float = 180.0,
        disable_buttons: bool = False,
    ):
        if timeout is None:
            raise TypeError("This view should not be used as a persistent view.")
        super().__init__(timeout=timeout)
        self.result: Optional[bool] = None
        self.author: Optional[discord.abc.User] = author
        self.message: Optional[discord.Message] = None
        self.disable_buttons = disable_buttons

    async def on_timeout(self):
        """
        A callback that is called by the provided (default) callbacks for `confirm_button`
        and `dismiss_button` as well as when a view's timeout elapses without being
        explicitly stopped.

        The default implementation will either disable the buttons
        when `disable_buttons` is ``True``, or remove the view from the message otherwise.

        .. note::

            This will not do anything if `message` is ``None``.
        """
        if self.message is None:
            # we can't do anything here if message is none
            return

        if self.disable_buttons:
            self.confirm_button.disabled = True
            self.dismiss_button.disabled = True
            view = self
        else:
            view = None
        try:
            await self.message.edit(view=view)
        except discord.HTTPException:
            # message could no longer be there or we may not be able to edit it anymore
            pass

    @discord.ui.button(label=_("Yes"), style=discord.ButtonStyle.green)
    async def confirm_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Warning: The Sphinx documentation for this method/attribute does not use this docstring.
        """
        A `discord.ui.Button` to confirm the message.

        The button's callback will set `result` to ``True``, defer the response,
        and call `on_timeout()` to clean up the view.

        Example
        -------
        Changing the style and label of this `discord.ui.Button`::

            view = ConfirmView(ctx.author)
            view.confirm_button.style = discord.ButtonStyle.red
            view.confirm_button.label = "Delete"
            view.dismiss_button.label = "Cancel"
            view.message = await ctx.send(
                "Are you sure you want to remove #very-important-channel?", view=view
            )
            await view.wait()
            if view.result:
                await ctx.send("Channel #very-important-channel deleted.")
            else:
                await ctx.send("Canceled.")
        """
        self.result = True
        self.stop()
        # respond to the interaction so the user does not see "interaction failed".
        await interaction.response.defer()
        # call `on_timeout` explicitly here since it's not called when `stop()` is called.
        await self.on_timeout()

    @discord.ui.button(label=_("No"), style=discord.ButtonStyle.red)
    async def dismiss_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Warning: The Sphinx documentation for this method/attribute does not use this docstring.
        """
        A `discord.ui.Button` to dismiss the message.

        The button's callback will set `result` to ``False``, defer the response,
        and call `on_timeout()` to clean up the view.

        Example
        -------
        Changing the style and label of this `discord.ui.Button`::

            view = ConfirmView(ctx.author)
            view.confirm_button.style = discord.ButtonStyle.red
            view.confirm_button.label = "Delete"
            view.dismiss_button.label = "Cancel"
            view.message = await ctx.send(
                "Are you sure you want to remove #very-important-channel?", view=view
            )
            await view.wait()
            if view.result:
                await ctx.send("Channel #very-important-channel deleted.")
            else:
                await ctx.send("Canceled.")
        """
        self.result = False
        self.stop()
        # respond to the interaction so the user does not see "interaction failed".
        await interaction.response.defer()
        # call `on_timeout` explicitly here since it's not called when `stop()` is called.
        await self.on_timeout()

    async def interaction_check(self, interaction: discord.Interaction):
        """
        A callback that is called when an interaction happens within the view
        that checks whether the view should process item callbacks for the interaction.

        The default implementation of this will assign value of `discord.Interaction.message`
        to the `message` attribute and either:

        - send an ephemeral failure message and return ``False``,
          if `author` is set and isn't the same as the interaction user, or
        - return ``True``

        .. seealso::

            The documentation of the callback in the base class:
            :meth:`discord.ui.View.interaction_check()`
        """
        if self.message is None:
            self.message = interaction.message
        if self.author and interaction.user.id != self.author.id:
            await interaction.response.send_message(
                content=_("You are not authorized to interact with this."), ephemeral=True
            )
            return False
        return True


class ContactDmReplyModal(discord.ui.Modal):
    def __init__(self, command: commands.Command, destination: discord.User):
        super().__init__(title=f"Reply to {destination}", timeout=None)
        self.command = command
        self.destination = destination
        self.message_input = discord.ui.TextInput(
            label="Message",
            style=discord.TextStyle.long,
            required=True,
        )
        self.add_item(self.message_input)

    async def on_submit(self, interaction: discord.Interaction):
        bot: "Red" = interaction.client
        message = self.message_input.value
        if self.command == bot.get_command("contact"):
            await self.contact(interaction, message)
        elif self.command == bot.get_command("dm"):
            await self.dm(interaction, message)

    async def contact(self, interaction: discord.Interaction, message: str):
        author = interaction.user
        bot: "Red" = interaction.client

        destinations = await bot.get_owner_notification_destinations()
        if not destinations:
            await interaction.response.send_message(_("I've been configured not to send this anywhere."), ephemeral=True)
            return

        guild = interaction.guild
        footer = _("User ID: {}").format(author.id)
        if guild:
            source = _("from {}").format(guild)
            footer += _(" | Server ID: {}").format(guild.id)
        else:
            source = _("through DM")

        prefixes = await bot.get_valid_prefixes()
        prefix = re.sub(rf"<@!?{bot.user.id}>", f"@{bot.user.name}".replace("\\", r"\\"), prefixes[0])
        content = _("Use `{}dm {} <text>` to reply to this user").format(prefix, author.id)
        description = _("Sent by {} {}").format(author, source)

        successful = False

        for destination in destinations:
            is_dm = isinstance(destination, discord.User)
            if not is_dm and not destination.permissions_for(destination.guild.me).send_messages:
                continue

            if await bot.embed_requested(destination):
                color = await bot.get_embed_color(destination)
                e = discord.Embed(colour=color, description=message)
                e.set_author(name=description, icon_url=author.display_avatar)
                e.set_footer(text=f"{footer}\n{content}")
                view = ContactDmView(bot.get_command("dm"), author)

                try:
                    await destination.send(embed=e, view=view)
                except discord.Forbidden:
                    log.exception(f"Contact failed to {destination}({destination.id})")
                except discord.HTTPException:
                    log.exception(
                        f"An unexpected error happened while attempting to"
                        f" send contact to {destination}({destination.id})"
                    )
                else:
                    successful = True
            else:
                msg_text = "{}\nMessage:\n\n{}\n{}".format(description, message, footer)
                try:
                    await destination.send("{}\n{}".format(content, box(msg_text)))
                except discord.Forbidden:
                    log.exception(f"Contact failed to {destination}({destination.id})")
                except discord.HTTPException:
                    log.exception(
                        f"An unexpected error happened while attempting to"
                        f" send contact to {destination}({destination.id})"
                    )
                else:
                    successful = True

        if successful:
            await interaction.response.send_message(_("Your message has been sent."), ephemeral=True)
        else:
            await interaction.response.send_message(_("I'm unable to deliver your message. Sorry."), ephemeral=True)

    async def dm(self, interaction: discord.Interaction, message: str):
        author = interaction.user
        bot: "Red" = interaction.client
        destination = self.destination

        description = _("Owner of {}").format(bot.user)
        content = _("You can reply to this message with {}contact").format(await bot.get_valid_prefixes()[0])

        if await bot.embed_requested(destination):
            e = discord.Embed(colour=await bot.get_embed_color(destination), description=message)
            e.set_footer(text=content)
            e.set_author(name=description, icon_url=bot.user.display_avatar)
            view = ContactDmView(bot.get_command("contact"), author)

            try:
                await destination.send(embed=e, view=view)
            except discord.HTTPException:
                await interaction.response.send_message(
                    _("Sorry, I couldn't deliver your message to {}").format(destination),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    _("Message delivered to {}").format(destination),
                    ephemeral=True
                )
        else:
            response = "{}\nMessage:\n\n{}".format(description, message)
            try:
                await destination.send("{}\n{}".format(box(response), content))
            except discord.HTTPException:
                await interaction.response.send_message(
                    _("Sorry, I couldn't deliver your message to {}").format(destination),
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    _("Message delivered to {}").format(destination),
                    ephemeral=True
                )

class ContactDmView(discord.ui.View):
    def __init__(self, command: commands.Command, destination: discord.User):
        super().__init__(timeout=None)
        self.command = command
        self.destination = destination

    @discord.ui.button(label="Reply", style=discord.ButtonStyle.gray)
    async def reply_button(self, interaction: discord.Interaction, button: discord.Button):
        modal = ContactDmReplyModal(self.command, self.destination)
        await interaction.response.send_modal(modal)

class InviteView(discord.ui.View):
    def __init__(self, bot: "Red"):
        super().__init__(timeout=None)
        self.bot = bot

    async def start(self, ctx: commands.Context, content: str = None, **kwargs):
        self.ctx = ctx
        bot_install = await self.bot.get_install_url()
        server_invite = "https://discord.gg/ggQ7GcPm7P"
        self.add_item(
            discord.ui.Button(
                style=discord.ButtonStyle.link,
                label=f"Install {self.bot.user.name}",
                url=bot_install,
                emoji=self.bot.get_emoji(1220931219169087508),
            )
        )
        if server_invite:
            self.add_item(
                discord.ui.Button(
                    style=discord.ButtonStyle.link,
                    label="Support Server",
                    url=server_invite,
                    emoji=self.bot.get_emoji(1220931046871273604),
                )
            )

        kwargs["reference"] = ctx.message.to_reference(fail_if_not_exists=False)
        kwargs["mention_author"] = False
        kwargs["view"] = self
        self.message = await ctx.send(content, **kwargs)


class View(discord.ui.View):
    """A subclass of ``discord.ui.View``

    Parameters
    -----------
    timeout: Optional[:class:`float`]
        Timeout in seconds from last interaction with the UI before no longer accepting input.
        If ``None`` then there is no timeout.

    Examples
    --------
        from redbot.core.utils.views import _StopButton, View

        view = View()
        view.add_item(_StopButton())
        await view.start(ctx, "Hello")
    """

    def __init__(self, *, timeout: Optional[float] = 180.0):
        super().__init__(timeout=timeout)

    async def start(self, ctx: commands.Context, content: str = None, **kwargs):
        self.author = ctx.author
        self.bot = ctx.bot
        self.ctx = ctx
        kwargs["reference"] = ctx.message.to_reference(fail_if_not_exists=False)
        kwargs["mention_author"] = False
        kwargs["view"] = self
        self.message = await ctx.send(content, **kwargs)

    async def interaction_check(self, interaction: discord.Interaction):
        if interaction.user != self.author:
            await interaction.response.send_message(
                _("You are not authorized to interact with this menu."), ephemeral=True
            )
            return False
        return True

    async def disable_items(self, interaction: discord.Interaction = None):
        for child in self.children:
            if hasattr(child, "style"):
                if child.style == discord.ButtonStyle.link:
                    continue
                child.style = discord.ButtonStyle.gray
            child.disabled = True
        # Interaction is optional here, since interaction can only be called once.
        if interaction:
            await interaction.response.edit_message(view=self)
            return
        await self.message.edit(view=self)

    async def on_timeout(self):
        await self.disable_items()
