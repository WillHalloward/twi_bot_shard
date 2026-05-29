"""Information commands cog for the Twi Bot Shard.

This module provides commands for displaying user, server, and role information.
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    ExternalServiceError,
    ValidationError,
)


async def user_info_function(
    interaction: discord.Interaction, member: discord.Member
) -> None:
    """Create and send an embed with detailed information about a Discord user."""
    try:
        if member is None:
            member = interaction.user

        if not member:
            raise ValidationError(message="Unable to identify the target user")

        logging.info(
            f"INFO USER: Request by {interaction.user.id} for user {member.id}"
        )

        user_color = (
            member.color
            if hasattr(member, "color") and member.color != discord.Color.default()
            else discord.Color(0x3CD63D)
        )
        embed = discord.Embed(
            title="👤 User Information",
            description=f"**{member.display_name}**\n{member.mention}",
            color=user_color,
            timestamp=discord.utils.utcnow(),
        )

        try:
            embed.set_thumbnail(url=member.display_avatar.url)
        except Exception as e:
            logging.warning(f"INFO USER: Could not set thumbnail: {e}")

        try:
            created_at = member.created_at.strftime("%d-%m-%Y @ %H:%M:%S")
            account_age = (discord.utils.utcnow() - member.created_at).days
            embed.add_field(
                name="📅 Account Created",
                value=f"{created_at}\n*({account_age} days ago)*",
                inline=True,
            )
        except Exception as e:
            logging.warning(f"INFO USER: Could not format creation date: {e}")
            embed.add_field(name="📅 Account Created", value="*Unknown*", inline=True)

        if hasattr(member, "joined_at") and member.joined_at:
            try:
                joined_at = member.joined_at.strftime("%d-%m-%Y @ %H:%M:%S")
                join_age = (discord.utils.utcnow() - member.joined_at).days
                embed.add_field(
                    name="🏠 Joined Server",
                    value=f"{joined_at}\n*({join_age} days ago)*",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO USER: Could not format join date: {e}")
                embed.add_field(name="🏠 Joined Server", value="*Unknown*", inline=True)
        else:
            embed.add_field(
                name="🏠 Server Status", value="*Not a server member*", inline=True
            )

        embed.add_field(
            name="🆔 User Details",
            value=f"**ID:** {member.id}\n**Username:** {member.name}\n**Bot:** {'Yes' if member.bot else 'No'}",
            inline=True,
        )

        if hasattr(member, "color"):
            color_hex = (
                str(member.color)
                if member.color != discord.Color.default()
                else "#000000"
            )
            embed.add_field(
                name="🎨 Color", value=f"{color_hex}\n{member.color}", inline=True
            )

        if hasattr(member, "status") and hasattr(member, "activity"):
            try:
                status_emoji = {
                    discord.Status.online: "🟢",
                    discord.Status.idle: "🟡",
                    discord.Status.dnd: "🔴",
                    discord.Status.offline: "⚫",
                }.get(member.status, "❓")

                status_text = f"{status_emoji} {member.status.name.title()}"
                if member.activity:
                    status_text += f"\n*{member.activity.name}*"

                embed.add_field(name="📊 Status", value=status_text, inline=True)
            except Exception as e:
                logging.warning(f"INFO USER: Could not get status: {e}")

        if hasattr(member, "roles") and len(member.roles) > 1:
            try:
                roles_list = [
                    role.mention
                    for role in reversed(member.roles)
                    if not role.is_default()
                ]

                if roles_list:
                    if len(roles_list) > 20:
                        roles_text = (
                            "\n".join(roles_list[:20])
                            + f"\n*... and {len(roles_list) - 20} more*"
                        )
                    else:
                        roles_text = "\n".join(roles_list)

                    embed.add_field(
                        name=f"🎭 Roles ({len(roles_list)})",
                        value=roles_text,
                        inline=False,
                    )
            except Exception as e:
                logging.warning(f"INFO USER: Could not format roles: {e}")

        if hasattr(member, "guild_permissions"):
            try:
                special_perms = []
                if member.guild_permissions.administrator:
                    special_perms.append("👑 Administrator")
                if member.guild_permissions.manage_guild:
                    special_perms.append("⚙️ Manage Server")
                if member.guild_permissions.manage_channels:
                    special_perms.append("📝 Manage Channels")
                if member.guild_permissions.manage_roles:
                    special_perms.append("🎭 Manage Roles")
                if member.guild_permissions.ban_members:
                    special_perms.append("🔨 Ban Members")
                if member.guild_permissions.kick_members:
                    special_perms.append("👢 Kick Members")

                if special_perms:
                    embed.add_field(
                        name="🔑 Key Permissions",
                        value="\n".join(special_perms[:6]),
                        inline=True,
                    )
            except Exception as e:
                logging.warning(f"INFO USER: Could not check permissions: {e}")

        embed.set_footer(text=f"Requested by {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed)

    except (ValidationError, ExternalServiceError):
        raise
    except discord.HTTPException as e:
        logging.error(f"INFO USER ERROR: Discord HTTP error: {e}")
        raise ExternalServiceError(
            message=f"Failed to send user information: {e}"
        ) from e
    except Exception as e:
        logging.error(f"INFO USER ERROR: {e}")
        raise ExternalServiceError(
            message=f"Unable to retrieve user information: {e}"
        ) from e


class Info(commands.Cog, name="Info"):
    """Information commands for users, servers, and roles."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.info_user_context = app_commands.ContextMenu(
            name="User info",
            callback=self.info_user_context_callback,
        )
        self.bot.tree.add_command(self.info_user_context)

    async def cog_unload(self) -> None:
        """Clean up context menu on unload."""
        self.bot.tree.remove_command(
            self.info_user_context.name, type=self.info_user_context.type
        )

    @app_commands.command(
        name="avatar", description="Posts the full version of a avatar"
    )
    @handle_interaction_errors
    async def av(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        """Display the full-size avatar of a user."""
        try:
            if member is None:
                member = interaction.user

            if not member:
                raise ValidationError(message="Unable to identify the target user")

            logging.info(
                f"INFO AVATAR: Request by {interaction.user.id} for user {member.id}"
            )

            try:
                if hasattr(member, "guild_avatar") and member.guild_avatar:
                    avatar_url = member.guild_avatar.url
                    avatar_type = "Server Avatar"
                    avatar_emoji = "🏠"
                else:
                    avatar_url = member.display_avatar.url
                    avatar_type = "Global Avatar"
                    avatar_emoji = "🌐"

                if not avatar_url:
                    raise ExternalServiceError(
                        message="Avatar URL could not be retrieved"
                    )

            except AttributeError as e:
                logging.warning(f"INFO AVATAR: Avatar attribute error: {e}")
                avatar_url = (
                    member.default_avatar.url
                    if hasattr(member, "default_avatar")
                    else None
                )
                avatar_type = "Default Avatar"
                avatar_emoji = "👤"

                if not avatar_url:
                    raise ExternalServiceError(
                        message="No avatar available for this user"
                    )

            embed = discord.Embed(
                title=f"{avatar_emoji} {avatar_type}",
                description=f"**{member.display_name}**\n{member.mention}",
                color=(
                    member.color
                    if hasattr(member, "color")
                    and member.color != discord.Color.default()
                    else discord.Color(0x3CD63D)
                ),
                timestamp=discord.utils.utcnow(),
            )

            embed.set_image(url=avatar_url)

            embed.add_field(
                name="👤 User Info",
                value=f"**ID:** {member.id}\n**Username:** {member.name}",
                inline=True,
            )

            try:
                avatar_format = avatar_url.split(".")[-1].split("?")[0].upper()
                embed.add_field(
                    name="🖼️ Format",
                    value=f"**Type:** {avatar_format}\n**High Resolution:** [Click here]({avatar_url})",
                    inline=True,
                )
            except Exception:
                embed.add_field(
                    name="🖼️ Direct Link",
                    value=f"[High Resolution]({avatar_url})",
                    inline=True,
                )

            if hasattr(member, "created_at"):
                embed.set_footer(
                    text=f"Account created: {member.created_at.strftime('%Y-%m-%d')}"
                )

            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            raise
        except discord.HTTPException as e:
            logging.error(f"INFO AVATAR ERROR: Discord HTTP error: {e}")
            raise ExternalServiceError(message=f"Failed to send avatar: {e}") from e
        except Exception as e:
            logging.error(f"INFO AVATAR ERROR: {e}")
            raise ExternalServiceError(message=f"Unable to display avatar: {e}") from e

    info = app_commands.Group(name="info", description="Information commands")

    @info.command(
        name="user",
        description="Gives the account information of a user.",
    )
    @handle_interaction_errors
    async def info_user(
        self, interaction: discord.Interaction, member: discord.Member = None
    ) -> None:
        """Display detailed information about a Discord user."""
        await user_info_function(interaction, member)

    @handle_interaction_errors
    async def info_user_context_callback(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        """Context menu command to display user information."""
        await user_info_function(interaction, member)

    @info.command(
        name="server",
        description="Gives the server information of the server the command was used in.",
    )
    @handle_interaction_errors
    async def info_server(self, interaction: discord.Interaction) -> None:
        """Display detailed information about the current Discord server."""
        try:
            if not interaction.guild:
                raise ValidationError(
                    message="This command can only be used in a server"
                )

            guild = interaction.guild
            logging.info(
                f"INFO SERVER: Request by {interaction.user.id} for guild {guild.id}"
            )

            embed = discord.Embed(
                title=f"🏰 {guild.name}",
                description=(
                    guild.description if guild.description else "*No description set*"
                ),
                color=discord.Color(0x3CD63D),
                timestamp=discord.utils.utcnow(),
            )

            try:
                if guild.icon:
                    embed.set_thumbnail(url=guild.icon.url)
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not set thumbnail: {e}")

            try:
                created_at = guild.created_at.strftime("%d-%m-%Y @ %H:%M:%S")
                server_age = (discord.utils.utcnow() - guild.created_at).days
                embed.add_field(
                    name="📅 Created",
                    value=f"{created_at}\n*({server_age} days ago)*",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not format creation date: {e}")
                embed.add_field(name="📅 Created", value="*Unknown*", inline=True)

            try:
                owner_text = guild.owner.mention if guild.owner else "*Unknown*"
                embed.add_field(
                    name="👑 Owner",
                    value=f"{owner_text}\n**ID:** {guild.id}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not get owner info: {e}")
                embed.add_field(
                    name="👑 Owner", value=f"*Unknown*\n**ID:** {guild.id}", inline=True
                )

            try:
                member_count = guild.member_count if guild.member_count else "Unknown"
                online_count = (
                    sum(1 for m in guild.members if m.status != discord.Status.offline)
                    if guild.members
                    else "Unknown"
                )
                embed.add_field(
                    name="👥 Members",
                    value=f"**Total:** {member_count}\n**Online:** {online_count}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not get member info: {e}")
                embed.add_field(name="👥 Members", value="*Unknown*", inline=True)

            try:
                role_count = len(guild.roles) - 1
                embed.add_field(
                    name="🎭 Roles",
                    value=f"**Count:** {role_count}/250\n**Highest:** {guild.roles[-1].mention if len(guild.roles) > 1 else '@everyone'}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not get role info: {e}")
                embed.add_field(name="🎭 Roles", value="*Unknown*", inline=True)

            try:
                text_channels = len(guild.text_channels)
                voice_channels = len(guild.voice_channels)
                categories = len(guild.categories)
                embed.add_field(
                    name="📝 Channels",
                    value=f"**Text:** {text_channels}\n**Voice:** {voice_channels}\n**Categories:** {categories}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not get channel info: {e}")
                embed.add_field(name="📝 Channels", value="*Unknown*", inline=True)

            try:
                normal_emojis = sum(1 for emoji in guild.emojis if not emoji.animated)
                animated_emojis = sum(1 for emoji in guild.emojis if emoji.animated)
                sticker_count = len(guild.stickers)

                embed.add_field(
                    name="😀 Emojis & Stickers",
                    value=f"**Static:** {normal_emojis}/{guild.emoji_limit}\n**Animated:** {animated_emojis}/{guild.emoji_limit}\n**Stickers:** {sticker_count}/{guild.sticker_limit}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not get emoji info: {e}")
                embed.add_field(
                    name="😀 Emojis & Stickers", value="*Unknown*", inline=True
                )

            try:
                active_threads = await guild.active_threads()
                thread_count = len(active_threads)
                embed.add_field(
                    name="🧵 Active Threads",
                    value=f"**Count:** {thread_count}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not get thread info: {e}")
                embed.add_field(
                    name="🧵 Active Threads", value="*Unknown*", inline=True
                )

            try:
                features_text = ""
                if guild.premium_tier > 0:
                    features_text += f"**Boost Level:** {guild.premium_tier}\n**Boosts:** {guild.premium_subscription_count}\n"

                if guild.verification_level:
                    features_text += (
                        f"**Verification:** {guild.verification_level.name.title()}\n"
                    )

                if guild.vanity_url:
                    features_text += f"**Vanity URL:** {guild.vanity_url}\n"

                if not features_text:
                    features_text = "*No special features*"

                embed.add_field(
                    name="✨ Features", value=features_text.strip(), inline=False
                )
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not get server features: {e}")

            try:
                if guild.banner:
                    embed.set_image(url=guild.banner.url)
            except Exception as e:
                logging.warning(f"INFO SERVER: Could not set banner: {e}")

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            raise
        except discord.HTTPException as e:
            logging.error(f"INFO SERVER ERROR: Discord HTTP error: {e}")
            raise ExternalServiceError(
                message=f"Failed to send server information: {e}"
            ) from e
        except Exception as e:
            logging.error(f"INFO SERVER ERROR: {e}")
            raise ExternalServiceError(
                message=f"Unable to retrieve server information: {e}"
            ) from e

    @info.command(
        name="role", description="Gives the role information of the role given."
    )
    @handle_interaction_errors
    async def info_role(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        """Display detailed information about a Discord role."""
        try:
            if not role:
                raise ValidationError(message="Unable to identify the target role")

            logging.info(
                f"INFO ROLE: Request by {interaction.user.id} for role {role.id}"
            )

            role_color = (
                discord.Color(role.color.value)
                if role.color.value != 0
                else discord.Color(0x3CD63D)
            )
            embed = discord.Embed(
                title=f"🎭 {role.name}",
                color=role_color,
                timestamp=discord.utils.utcnow(),
            )

            try:
                created_at = role.created_at.strftime("%d-%m-%Y @ %H:%M:%S")
                role_age = (discord.utils.utcnow() - role.created_at).days
                embed.add_field(
                    name="📅 Created",
                    value=f"{created_at}\n*({role_age} days ago)*",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO ROLE: Could not format creation date: {e}")
                embed.add_field(name="📅 Created", value="*Unknown*", inline=True)

            try:
                position = role.position
                total_roles = len(role.guild.roles) if role.guild else "Unknown"
                embed.add_field(
                    name="🆔 Details",
                    value=f"**ID:** {role.id}\n**Position:** {position}/{total_roles}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO ROLE: Could not get role details: {e}")
                embed.add_field(
                    name="🆔 Details",
                    value=f"**ID:** {role.id}\n**Position:** *Unknown*",
                    inline=True,
                )

            try:
                color_hex = (
                    hex(role.color.value) if role.color.value != 0 else "#000000"
                )
                color_rgb = f"({role.color.r}, {role.color.g}, {role.color.b})"
                embed.add_field(
                    name="🎨 Color",
                    value=f"**Hex:** {color_hex}\n**RGB:** {color_rgb}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO ROLE: Could not get color info: {e}")
                embed.add_field(name="🎨 Color", value="*Unknown*", inline=True)

            try:
                properties = []
                if role.hoist:
                    properties.append("📌 Hoisted")
                if role.mentionable:
                    properties.append("📢 Mentionable")
                if role.managed:
                    properties.append("🤖 Managed")
                if role.is_default():
                    properties.append("👥 Default Role")
                if role.is_premium_subscriber():
                    properties.append("💎 Booster Role")
                if role.is_bot_managed():
                    properties.append("🤖 Bot Role")
                if role.is_integration():
                    properties.append("🔗 Integration Role")

                properties_text = (
                    "\n".join(properties) if properties else "*No special properties*"
                )
                embed.add_field(name="⚙️ Properties", value=properties_text, inline=True)
            except Exception as e:
                logging.warning(f"INFO ROLE: Could not get properties: {e}")
                embed.add_field(name="⚙️ Properties", value="*Unknown*", inline=True)

            try:
                member_count = len(role.members)
                total_members = (
                    role.guild.member_count
                    if role.guild and role.guild.member_count
                    else "Unknown"
                )
                percentage = (
                    f"({member_count / role.guild.member_count * 100:.1f}%)"
                    if role.guild and role.guild.member_count
                    else ""
                )

                embed.add_field(
                    name="👥 Members",
                    value=f"**Count:** {member_count}/{total_members}\n{percentage}",
                    inline=True,
                )
            except Exception as e:
                logging.warning(f"INFO ROLE: Could not get member count: {e}")
                embed.add_field(name="👥 Members", value="*Unknown*", inline=True)

            try:
                key_perms = []
                if role.permissions.administrator:
                    key_perms.append("👑 Administrator")
                if role.permissions.manage_guild:
                    key_perms.append("⚙️ Manage Server")
                if role.permissions.manage_channels:
                    key_perms.append("📝 Manage Channels")
                if role.permissions.manage_roles:
                    key_perms.append("🎭 Manage Roles")
                if role.permissions.ban_members:
                    key_perms.append("🔨 Ban Members")
                if role.permissions.kick_members:
                    key_perms.append("👢 Kick Members")
                if role.permissions.manage_messages:
                    key_perms.append("🗑️ Manage Messages")
                if role.permissions.mention_everyone:
                    key_perms.append("📢 Mention Everyone")

                if key_perms:
                    perms_text = "\n".join(key_perms[:8])
                    if len(key_perms) > 8:
                        perms_text += f"\n*... and {len(key_perms) - 8} more*"
                else:
                    perms_text = "*No special permissions*"

                embed.add_field(
                    name="🔑 Key Permissions", value=perms_text, inline=False
                )
            except Exception as e:
                logging.warning(f"INFO ROLE: Could not get permissions: {e}")
                embed.add_field(
                    name="🔑 Key Permissions", value="*Unknown*", inline=False
                )

            try:
                embed.add_field(
                    name="📝 Mention",
                    value=f"`{role.mention}` → {role.mention}",
                    inline=False,
                )
            except Exception as e:
                logging.warning(f"INFO ROLE: Could not format mention: {e}")

            embed.set_footer(text=f"Requested by {interaction.user.display_name}")
            await interaction.response.send_message(embed=embed)

        except (ValidationError, ExternalServiceError):
            raise
        except discord.HTTPException as e:
            logging.error(f"INFO ROLE ERROR: Discord HTTP error: {e}")
            raise ExternalServiceError(
                message=f"Failed to send role information: {e}"
            ) from e
        except Exception as e:
            logging.error(f"INFO ROLE ERROR: {e}")
            raise ExternalServiceError(
                message=f"Unable to retrieve role information: {e}"
            ) from e


async def setup(bot: commands.Bot) -> None:
    """Set up the Info cog."""
    await bot.add_cog(Info(bot))
