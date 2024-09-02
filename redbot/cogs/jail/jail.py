
import discord
from redbot.core import commands, Config
import asyncio

class Jail(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=1234567890, force_registration=True)
        self.config.register_guild(jail_role=None, jail_channel=None, jailed_users={})

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def setrole(self, ctx, role: discord.Role):
        """Set the jail role."""
        await self.config.guild(ctx.guild).jail_role.set(role.id)
        await ctx.send(f"Jail role set to {role.name}")

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def setjail(self, ctx, channel: discord.TextChannel):
        """Set the jail channel."""
        await self.config.guild(ctx.guild).jail_channel.set(channel.id)

        # Remove access of the jail role to all channels but the jail channel
        jail_role_id = await self.config.guild(ctx.guild).jail_role()
        if not jail_role_id:
            await ctx.send("Jail role is not set. Please set it first using `setrole`.")
            return
        jail_role = ctx.guild.get_role(jail_role_id)
        if not jail_role:
            await ctx.send("Jail role not found. Please set it again using `setrole`.")
            return

        for chan in ctx.guild.channels:
            try:
                if chan == channel:
                    await chan.set_permissions(jail_role, read_messages=True, send_messages=True)
                else:
                    await chan.set_permissions(jail_role, read_messages=False, send_messages=False)
            except discord.Forbidden:
                await ctx.send(f"Failed to update permissions for {chan.name}. Missing permissions: Manage Channels.")
            except discord.HTTPException as e:
                await ctx.send(f"Failed to update permissions for {chan.name}. HTTPException: {e}")

        await ctx.send(f"Jail channel set to {channel.name} and permissions updated.")
            
    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def jail(self, ctx, user: discord.Member, time: str, *, reason: str = "Breaking rules or under investigation"):
        """Jail a user for a specified time."""
        jail_role_id = await self.config.guild(ctx.guild).jail_role()
        jail_channel_id = await self.config.guild(ctx.guild).jail_channel()
    
        if not jail_role_id or not jail_channel_id:
            await ctx.send("Jail role or jail channel is not set. Please set them using `setrole` and `setjail`.")
            return

        jail_role = ctx.guild.get_role(jail_role_id)
        if not jail_role:
            await ctx.send("Jail role not found. Please set it again using `setrole`.")
            return

        # Parse time
        time_seconds = self.parse_time(time)
        if time_seconds is None:
            await ctx.send("Invalid time format. Please use a valid format like `1h`, `30m`, etc.")
            return

        # Save user's roles
        original_roles = [role.id for role in user.roles if role != ctx.guild.default_role]
        
        jailed_users_data = await self.config.guild(ctx.guild).jailed_users()
        if not isinstance(jailed_users_data, dict):
            jailed_users_data = {}
        
        jailed_users_data[str(user.id)] = {"roles": original_roles}
        
        await self.config.guild(ctx.guild).jailed_users.set(jailed_users_data)
        
        # Add jail role and remove original roles
        await user.add_roles(jail_role)
        await user.remove_roles(*[ctx.guild.get_role(role_id) for role_id in original_roles])

        await ctx.send(f"{user.mention} has been jailed for {time} for: {reason}")

        # Wait for the specified time
        await asyncio.sleep(time_seconds)

        # Free the user after the time has passed
        await self.free_user(ctx.guild, user)

    @commands.command()
    @commands.guild_only()
    @commands.admin_or_permissions(manage_roles=True)
    async def free(self, ctx, user: discord.Member):
        """Free a jailed user immediately."""
        await self.free_user(ctx.guild, user)
        await ctx.send(f"{user.mention} has been freed.")

    async def free_user(self, guild, user):
        jail_role_id = await self.config.guild(guild).jail_role()
        if not jail_role_id:
            return
        jail_role = guild.get_role(jail_role_id)
        if not jail_role:
            return

        # Remove jail role and restore original roles
        try:
            await user.remove_roles(jail_role)
            original_roles = await self.config.guild(guild).jailed_users.get_raw(str(user.id), "roles", default=[])
            roles = [guild.get_role(role_id) for role_id in original_roles if guild.get_role(role_id)]
            await user.add_roles(*roles)

            jail_channel_id = await self.config.guild(guild).jail_channel()
            jail_channel = guild.get_channel(jail_channel_id)
            if jail_channel:
                jail_message_id = await self.config.guild(guild).jailed_users.get_raw(str(user.id), "jail_message_id", default=None)
                if jail_message_id:
                    try:
                        jail_message = await jail_channel.fetch_message(jail_message_id)
                        await jail_message.delete()
                    except discord.NotFound:
                        pass
                    except discord.Forbidden:
                        await guild.system_channel.send(f"Failed to delete jail message for {user.mention}. Missing permissions: Manage Messages.")
                    except discord.HTTPException as e:
                        await guild.system_channel.send(f"Failed to delete jail message for {user.mention}. HTTPException: {e}")

        except discord.Forbidden:
            await guild.system_channel.send(f"Failed to remove jail role from {user.mention}. Missing permissions: Manage Roles.")
        except discord.HTTPException as e:
            await guild.system_channel.send(f"Failed to remove jail role from {user.mention}. HTTPException: {e}")

        # Remove user from jailed users list
        await self.config.guild(guild).jailed_users.clear_raw(str(user.id))

    def parse_time(self, time_str):
        units = {'h': 3600, 'm': 60, 's': 1}
        try:
            return int(time_str[:-1]) * units[time_str[-1]]
        except (ValueError, KeyError):
            return None
