########## SENSITIVE SECTION WARNING ###########
################################################
# Any edits of any of the exported names       #
# may result in a breaking change.             #
# Ensure no names are removed without warning. #
################################################

### DEP-WARN: Check this *every* discord.py update
from discord.app_commands import (
    AllChannels as AllChannels,
    AppCommand as AppCommand,
    AppCommandChannel as AppCommandChannel,
    AppCommandContext as AppCommandContext,
    AppCommandError as AppCommandError,
    AppCommandGroup as AppCommandGroup,
    AppCommandPermissions as AppCommandPermissions,
    AppCommandThread as AppCommandThread,
    AppInstallationType as AppInstallationType,
    Argument as Argument,
    BotMissingPermissions as BotMissingPermissions,
    Command as Command,
    CommandAlreadyRegistered as CommandAlreadyRegistered,
    CommandInvokeError as CommandInvokeError,
    CommandLimitReached as CommandLimitReached,
    CommandNotFound as CommandNotFound,
    CommandOnCooldown as CommandOnCooldown,
    CommandSignatureMismatch as CommandSignatureMismatch,
    CommandSyncFailure as CommandSyncFailure,
    CommandTree as CommandTree,
    ContextMenu as ContextMenu,
    Cooldown as Cooldown,
    Group as Group,
    GuildAppCommandPermissions as GuildAppCommandPermissions,
    MissingAnyRole as MissingAnyRole,
    MissingApplicationID as MissingApplicationID,
    MissingPermissions as MissingPermissions,
    MissingRole as MissingRole,
    Namespace as Namespace,
    NoPrivateMessage as NoPrivateMessage,
    Parameter as Parameter,
    Range as Range,
    Transform as Transform,
    Transformer as Transformer,
    TransformerError as TransformerError,
    TranslationContext as TranslationContext,
    TranslationContextLocation as TranslationContextLocation,
    TranslationContextTypes as TranslationContextTypes,
    TranslationError as TranslationError,
    Translator as Translator,
    allowed_contexts as allowed_contexts,
    allowed_installs as allowed_installs,
    autocomplete as autocomplete,
    check as check,
    CheckFailure as CheckFailure,
    Choice as Choice,
    choices as choices,
    command as command,
    context_menu as context_menu,
    default_permissions as default_permissions,
    describe as describe,
    dm_only as dm_only,
    guild_install as guild_install,
    guild_only as guild_only,
    guilds as guilds,
    locale_str as locale_str,
    private_channel_only as private_channel_only,
    rename as rename,
    user_install as user_install,
)

from . import checks as checks
from .errors import (
    UserFeedbackCheckFailure as UserFeedbackCheckFailure,
)

__all__ = (
    "AllChannels",
    "AppCommand",
    "AppCommandChannel",
    "AppCommandContext",
    "AppCommandError",
    "AppCommandGroup",
    "AppCommandPermissions",
    "AppCommandThread",
    "AppInstallationType",
    "Argument",
    "BotMissingPermissions",
    "Command",
    "CommandAlreadyRegistered",
    "CommandInvokeError",
    "CommandLimitReached",
    "CommandNotFound",
    "CommandOnCooldown",
    "CommandSignatureMismatch",
    "CommandSyncFailure",
    "CommandTree",
    "ContextMenu",
    "Cooldown",
    "Group",
    "GuildAppCommandPermissions",
    "MissingAnyRole",
    "MissingApplicationID",
    "MissingPermissions",
    "MissingRole",
    "Namespace",
    "NoPrivateMessage",
    "Parameter",
    "Range",
    "Transform",
    "Transformer",
    "TransformerError",
    "TranslationContext",
    "TranslationContextLocation",
    "TranslationContextTypes",
    "TranslationError",
    "Translator",
    "allowed_contexts",
    "allowed_installs",
    "autocomplete",
    "check",
    "CheckFailure",
    "Choice",
    "choices",
    "command",
    "context_menu",
    "default_permissions",
    "describe",
    "dm_only",
    "guild_install",
    "guild_only",
    "guilds",
    "locale_str",
    "private_channel_only",
    "rename",
    "user_install",
    "checks",
    "UserFeedbackCheckFailure",
)