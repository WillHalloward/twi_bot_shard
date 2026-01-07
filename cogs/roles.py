"""Role management cog for the Twi Bot Shard.

This module provides commands for self-assignable roles and role administration.
"""

import logging
import re
from itertools import groupby

import discord
from discord import app_commands
from discord.ext import commands

import config
from utils.error_handling import handle_interaction_errors
from utils.exceptions import (
    DatabaseError,
    ExternalServiceError,
    PermissionError,
    ValidationError,
)
from utils.permissions import app_admin_or_me_check


class Roles(commands.Cog, name="Roles"):
    """Role management commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.category_cache = None

    async def cog_load(self) -> None:
        """Load category cache on cog load."""
        try:
            self.category_cache = await self.bot.db.fetch(
                "SELECT DISTINCT (category) FROM roles WHERE category IS NOT NULL"
            )
            logging.info(
                f"ROLES: Successfully loaded category cache with {len(self.category_cache)} categories"
            )
        except Exception as e:
            logging.error(f"ROLES: Failed to load category cache: {e}")
            self.category_cache = []

    @app_commands.command(
        name="roles",
        description="Posts all the roles in the server you can assign yourself",
    )
    @handle_interaction_errors
    async def role_list(self, interaction: discord.Interaction) -> None:
        """Display a list of all self-assignable roles in the server."""
        try:
            if not interaction.guild:
                raise ValidationError(
                    message="This command can only be used in a server"
                )

            logging.info(
                f"ROLES LIST: Role list request by user {interaction.user.id} in guild {interaction.guild.id}"
            )

            try:
                user_roles = [role.id for role in interaction.user.roles]
            except Exception as e:
                logging.warning(
                    f"ROLES LIST WARNING: Could not get user roles for {interaction.user.id}: {e}"
                )
                user_roles = []

            try:
                roles = await self.bot.db.fetch(
                    "SELECT id, name, required_roles, weight, category "
                    "FROM roles "
                    "WHERE (required_roles && $2::bigint[] OR required_roles is NULL) "
                    "AND guild_id = $1 "
                    "AND self_assignable = TRUE "
                    "ORDER BY weight, name DESC",
                    interaction.guild.id,
                    user_roles,
                )
            except Exception as e:
                logging.error(
                    f"ROLES LIST ERROR: Database query failed for guild {interaction.guild.id}: {e}"
                )
                raise DatabaseError(message=f"Failed to retrieve role list: {e}") from e

            if not roles:
                embed = discord.Embed(
                    title="Self-Assignable Roles",
                    description="No self-assignable roles are currently available.",
                    color=discord.Color.orange(),
                    timestamp=discord.utils.utcnow(),
                )

                embed.add_field(
                    name="Setup Required",
                    value="No roles have been configured for self-assignment on this server.\n\n**For Administrators:**\nUse `/admin_role add` to add roles to the self-assignment list.",
                    inline=False,
                )

                embed.add_field(
                    name="What are self-assignable roles?",
                    value="Self-assignable roles allow users to give themselves specific roles without needing administrator intervention. Common examples include:\n- Notification preferences\n- Game roles\n- Interest groups\n- Pronouns",
                    inline=False,
                )

                embed.set_footer(text="Contact a moderator for more information")

                logging.info(
                    f"ROLES LIST: No self-assignable roles found for guild {interaction.guild.id}"
                )
                await interaction.response.send_message(embed=embed)
                return

            embed = discord.Embed(
                title="Self-Assignable Roles",
                description=f"**Server:** {interaction.guild.name}\n**Available Roles:** {len(roles)}\n\n*Use `/role <role>` to assign yourself a role*",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow(),
            )

            try:
                if interaction.guild.icon:
                    embed.set_thumbnail(url=interaction.guild.icon.url)
            except Exception as e:
                logging.warning(
                    f"ROLES LIST WARNING: Could not set thumbnail for guild {interaction.guild.id}: {e}"
                )

            try:
                roles.sort(
                    key=lambda k: (k["category"] or "Uncategorized", k["weight"] or 0)
                )
            except Exception as e:
                logging.warning(f"ROLES LIST WARNING: Could not sort roles: {e}")

            try:
                for key, group in groupby(
                    roles, key=lambda k: k["category"] or "Uncategorized"
                ):
                    role_mentions = ""
                    role_count = 0
                    field_number = 1

                    for row in group:
                        try:
                            role = interaction.guild.get_role(row["id"])
                            if role:
                                temp_str = f"{role.mention}\n"
                                role_count += 1

                                if len(temp_str + role_mentions) > 1000:
                                    embed.add_field(
                                        name=f"**{key.title()}**"
                                        + (
                                            f" ({field_number})"
                                            if field_number > 1
                                            else ""
                                        ),
                                        value=role_mentions.strip() or "*No roles*",
                                        inline=False,
                                    )
                                    role_mentions = temp_str
                                    field_number += 1
                                else:
                                    role_mentions += temp_str
                            else:
                                logging.warning(
                                    f"ROLES LIST WARNING: Role {row['id']} not found in guild {interaction.guild.id}"
                                )
                        except Exception as e:
                            logging.warning(
                                f"ROLES LIST WARNING: Error processing role {row.get('id', 'unknown')}: {e}"
                            )
                            continue

                    if role_mentions.strip():
                        embed.add_field(
                            name=f"**{key.title()}**"
                            + (f" ({field_number})" if field_number > 1 else ""),
                            value=role_mentions.strip(),
                            inline=False,
                        )

            except Exception as e:
                logging.error(
                    f"ROLES LIST ERROR: Error building role list for guild {interaction.guild.id}: {e}"
                )
                raise ExternalServiceError(
                    message=f"Failed to format role list: {e}"
                ) from e

            embed.set_footer(
                text="Use /role <role> to assign | /role <role> again to remove"
            )

            logging.info(
                f"ROLES LIST: Successfully generated role list with {len(roles)} roles for guild {interaction.guild.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, DatabaseError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"ROLES LIST ERROR: Unexpected error for guild {interaction.guild.id if interaction.guild else 'unknown'}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while listing roles: {e}"
            ) from e

    admin_role = app_commands.Group(
        name="admin_role", description="Admin role commands"
    )

    @admin_role.command(name="weight", description="Changes the weight of a role")
    @app_commands.check(app_admin_or_me_check)
    @handle_interaction_errors
    async def update_role_weight(
        self, interaction: discord.Interaction, role: discord.role.Role, new_weight: int
    ) -> None:
        """Change the weight of a role in the role list."""
        try:
            if not interaction.guild:
                raise ValidationError(
                    message="This command can only be used in a server"
                )

            if not role:
                raise ValidationError(message="Role is required")

            if new_weight < -1000 or new_weight > 1000:
                raise ValidationError(message="Weight must be between -1000 and 1000")

            logging.info(
                f"ROLES WEIGHT: Role weight update request by admin {interaction.user.id} "
                f"for role {role.id} ({role.name}) to weight {new_weight}"
            )

            try:
                existing_role = await self.bot.db.fetchrow(
                    "SELECT id, name, weight, category, self_assignable FROM roles WHERE id = $1 AND guild_id = $2",
                    role.id,
                    interaction.guild.id,
                )
            except Exception as e:
                logging.error(
                    f"ROLES WEIGHT ERROR: Database lookup failed for role {role.id}: {e}"
                )
                raise DatabaseError(
                    message=f"Failed to lookup role in database: {e}"
                ) from e

            if not existing_role:
                embed = discord.Embed(
                    title="Role Not Found",
                    description=f"**Role:** {role.mention}",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )
                embed.add_field(
                    name="Role Not in Database",
                    value=f"The role {role.mention} is not configured in the role system.\n\n**To add it:**\nUse `/admin_role add {role.mention}` first.",
                    inline=False,
                )
                embed.set_footer(
                    text="Only configured roles can have their weight changed"
                )

                await interaction.response.send_message(embed=embed)
                return

            old_weight = existing_role.get("weight", 0)

            try:
                result = await self.bot.db.execute(
                    "UPDATE roles SET weight = $1 WHERE id = $2 AND guild_id = $3",
                    new_weight,
                    role.id,
                    interaction.guild.id,
                )

                if result == "UPDATE 0":
                    raise DatabaseError(
                        message="No rows were updated - role may not exist"
                    )

            except Exception as e:
                logging.error(
                    f"ROLES WEIGHT ERROR: Database update failed for role {role.id}: {e}"
                )
                raise DatabaseError(message=f"Failed to update role weight: {e}") from e

            embed = discord.Embed(
                title="Role Weight Updated",
                description=f"**Role:** {role.mention}",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="Weight Change",
                value=f"**Old Weight:** {old_weight}\n**New Weight:** {new_weight}\n**Change:** {new_weight - old_weight:+d}",
                inline=True,
            )

            embed.add_field(
                name="Role Info",
                value=f"**Category:** {existing_role.get('category', 'Uncategorized')}\n**Self-Assignable:** {'Yes' if existing_role.get('self_assignable') else 'No'}",
                inline=True,
            )

            embed.add_field(
                name="Updated By",
                value=f"{interaction.user.mention}\n**ID:** {interaction.user.id}",
                inline=True,
            )

            embed.add_field(
                name="Weight Info",
                value="Lower weights appear higher in the role list within their category. Negative weights are allowed for priority roles.",
                inline=False,
            )

            embed.set_footer(text="Use /roles to see the updated role list")

            logging.info(
                f"ROLES WEIGHT: Successfully updated role {role.id} weight from {old_weight} to {new_weight} by admin {interaction.user.id}"
            )
            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError, ExternalServiceError):
            raise
        except Exception as e:
            logging.error(
                f"ROLES WEIGHT ERROR: Unexpected error for role {role.id if role else 'unknown'}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while updating role weight: {e}"
            ) from e

    @admin_role.command(name="add", description="Adds a role to the self assign list")
    @app_commands.check(app_admin_or_me_check)
    @handle_interaction_errors
    async def role_add(
        self,
        interaction: discord.Interaction,
        role: discord.role.Role,
        category: str = "Uncategorized",
        auto_replace: bool = False,
        required_roles: str = None,
    ) -> None:
        """Add a role to the self-assignable roles list."""
        try:
            if not role:
                raise ValidationError(message="Role parameter is required")

            if not interaction.guild:
                raise ValidationError(
                    message="This command can only be used in a server"
                )

            if len(category) > 50:
                raise ValidationError(
                    message="Category name must be 50 characters or less"
                )

            if role >= interaction.guild.me.top_role:
                raise PermissionError(
                    message=f"I cannot manage {role.mention} as it's higher than my highest role"
                )

            list_of_roles = None
            if required_roles is not None:
                list_of_roles = []
                required_roles_list = required_roles.split()

                for user_role in required_roles_list:
                    matched_id = re.search(r"\d+", user_role)
                    if matched_id:
                        role_id = int(matched_id.group())
                        temp = discord.utils.get(interaction.guild.roles, id=role_id)
                        if temp:
                            list_of_roles.append(temp.id)
                        else:
                            raise ValidationError(
                                message=f"Role with ID {role_id} not found in this server"
                            )
                    else:
                        raise ValidationError(
                            message=f"Could not parse role: {user_role}"
                        )

            logging.info(
                f"ROLES ADD: User {interaction.user.id} adding role {role.id} ({role.name}) to self-assign list with category '{category}'"
            )

            existing_role = await self.bot.db.fetchrow(
                "SELECT self_assignable FROM roles WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            if existing_role and existing_role["self_assignable"]:
                raise ValidationError(
                    message=f"{role.mention} is already in the self-assign list"
                )

            await self.bot.db.execute(
                "UPDATE roles SET self_assignable = TRUE, required_roles = $1, alias = $2, category = $3, auto_replace = $4 "
                "WHERE id = $2 AND guild_id = $5",
                list_of_roles,
                role.id,
                category.lower(),
                auto_replace,
                interaction.guild.id,
            )

            embed = discord.Embed(
                title="Role Added to Self-Assign List",
                description=f"Successfully added {role.mention} to the self-assignable roles",
                color=discord.Color.green(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(name="Category", value=category, inline=True)

            embed.add_field(
                name="Auto Replace",
                value="Yes" if auto_replace else "No",
                inline=True,
            )

            if list_of_roles:
                required_role_mentions = []
                for role_id in list_of_roles:
                    req_role = interaction.guild.get_role(role_id)
                    if req_role:
                        required_role_mentions.append(req_role.mention)

                embed.add_field(
                    name="Required Roles",
                    value=(
                        ", ".join(required_role_mentions)
                        if required_role_mentions
                        else "None"
                    ),
                    inline=False,
                )
            else:
                embed.add_field(name="Required Roles", value="None", inline=False)

            embed.set_footer(text="Users can now assign this role using /role")

            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError):
            raise
        except discord.Forbidden as e:
            logging.error(
                f"ROLES ADD ERROR: Permission error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise PermissionError(
                message=f"I don't have permission to manage roles: {e}"
            ) from e
        except Exception as e:
            logging.error(
                f"ROLES ADD ERROR: Unexpected error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise DatabaseError(
                message=f"Unexpected error while adding role to self-assign list: {e}"
            ) from e

    @role_add.autocomplete("category")
    async def role_add_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        """Provide autocomplete suggestions for role categories."""
        return [
            app_commands.Choice(name=category["category"], value=category["category"])
            for category in self.category_cache
            if current.lower() in category["category"].lower() or current == ""
        ][0:25]

    @admin_role.command(
        name="remove", description="removes a role from the self assign list"
    )
    @app_commands.check(app_admin_or_me_check)
    @handle_interaction_errors
    async def role_remove(
        self, interaction: discord.Interaction, role: discord.Role
    ) -> None:
        """Remove a role from the self-assignable roles list."""
        try:
            if not role:
                raise ValidationError(message="Role parameter is required")

            if not interaction.guild:
                raise ValidationError(
                    message="This command can only be used in a server"
                )

            logging.info(
                f"ROLES REMOVE: User {interaction.user.id} removing role {role.id} ({role.name}) from self-assign list"
            )

            existing_role = await self.bot.db.fetchrow(
                "SELECT self_assignable, category FROM roles WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            if not existing_role:
                raise ValidationError(
                    message=f"{role.mention} is not tracked in the database"
                )

            if not existing_role["self_assignable"]:
                raise ValidationError(
                    message=f"{role.mention} is not currently in the self-assign list"
                )

            await self.bot.db.execute(
                "UPDATE roles SET self_assignable = FALSE, weight = 0, alias = NULL, category = NULL, required_roles = NULL, auto_replace = FALSE "
                "WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            embed = discord.Embed(
                title="Role Removed from Self-Assign List",
                description=f"Successfully removed {role.mention} from the self-assignable roles",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow(),
            )

            embed.add_field(
                name="Removed Role",
                value=f"{role.mention}\n**ID:** {role.id}",
                inline=True,
            )

            if existing_role["category"]:
                embed.add_field(
                    name="Previous Category",
                    value=existing_role["category"],
                    inline=True,
                )

            embed.add_field(
                name="Status",
                value="All role settings have been reset to defaults",
                inline=False,
            )

            embed.set_footer(text="Users can no longer assign this role using /role")

            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError):
            raise
        except Exception as e:
            logging.error(
                f"ROLES REMOVE ERROR: Unexpected error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise DatabaseError(
                message=f"Unexpected error while removing role from self-assign list: {e}"
            ) from e

    @app_commands.command(
        name="role", description="Adds or removes a role from yourself"
    )
    @handle_interaction_errors
    async def role(self, interaction: discord.Interaction, role: discord.Role) -> None:
        """Add or remove a self-assignable role from yourself."""
        try:
            if not role:
                raise ValidationError(message="Role parameter is required")

            if not interaction.guild:
                raise ValidationError(
                    message="This command can only be used in a server"
                )

            if not isinstance(interaction.user, discord.Member):
                raise ValidationError(message="This command requires a server member")

            if role >= interaction.guild.me.top_role:
                raise PermissionError(
                    message=f"I cannot manage {role.mention} as it's higher than my highest role"
                )

            logging.info(
                f"ROLES: User {interaction.user.id} requesting role toggle for {role.id} ({role.name})"
            )

            s_role = await self.bot.db.fetchrow(
                "SELECT * FROM roles WHERE id = $1 AND guild_id = $2",
                role.id,
                interaction.guild.id,
            )

            if not s_role:
                raise ValidationError(
                    message=f"{role.mention} is not tracked in the database"
                )

            if not s_role["self_assignable"]:
                raise ValidationError(
                    message=f"{role.mention} is not available for self-assignment"
                )

            user_role_ids = [r.id for r in interaction.user.roles]

            if s_role["required_roles"] is not None:
                required_roles = s_role["required_roles"]
                has_required = any(
                    req_role_id in user_role_ids for req_role_id in required_roles
                )

                if not has_required:
                    required_role_names = []
                    for req_role_id in required_roles:
                        req_role = interaction.guild.get_role(req_role_id)
                        if req_role:
                            required_role_names.append(req_role.mention)

                    required_text = (
                        ", ".join(required_role_names)
                        if required_role_names
                        else "specified roles"
                    )
                    raise ValidationError(
                        message=f"You need one of these roles to access {role.mention}: {required_text}"
                    )

            action = "remove" if role in interaction.user.roles else "add"

            if action == "remove":
                await interaction.user.remove_roles(
                    role, reason=f"Self-role removal by {interaction.user}"
                )

                embed = discord.Embed(
                    title="Role Removed",
                    description=f"Successfully removed {role.mention} from your roles",
                    color=discord.Color.red(),
                    timestamp=discord.utils.utcnow(),
                )

                logging.info(
                    f"ROLES: Successfully removed role {role.id} from user {interaction.user.id}"
                )

            else:
                if s_role["auto_replace"] and s_role["category"]:
                    category_roles = await self.bot.db.fetch(
                        "SELECT id FROM roles WHERE id = ANY($1::bigint[]) AND category = $2 AND guild_id = $3",
                        user_role_ids,
                        s_role["category"],
                        interaction.guild.id,
                    )

                    removed_roles = []
                    for category_role_data in category_roles:
                        category_role = interaction.guild.get_role(
                            category_role_data["id"]
                        )
                        if category_role and category_role in interaction.user.roles:
                            await interaction.user.remove_roles(
                                category_role, reason=f"Auto-replace for {role.name}"
                            )
                            removed_roles.append(category_role.mention)

                await interaction.user.add_roles(
                    role, reason=f"Self-role assignment by {interaction.user}"
                )

                embed = discord.Embed(
                    title="Role Added",
                    description=f"Successfully added {role.mention} to your roles",
                    color=discord.Color.green(),
                    timestamp=discord.utils.utcnow(),
                )

                if (
                    s_role["auto_replace"]
                    and "removed_roles" in locals()
                    and removed_roles
                ):
                    embed.add_field(
                        name="Auto-Replaced Roles",
                        value=", ".join(removed_roles),
                        inline=False,
                    )

                logging.info(
                    f"ROLES: Successfully added role {role.id} to user {interaction.user.id}"
                )

            embed.add_field(
                name="Role", value=f"{role.mention}\n**ID:** {role.id}", inline=True
            )

            if s_role["category"]:
                embed.add_field(name="Category", value=s_role["category"], inline=True)

            embed.set_footer(text=f"Action: {action.title()}")
            await interaction.response.send_message(embed=embed)

        except (ValidationError, PermissionError, DatabaseError, ExternalServiceError):
            raise
        except discord.Forbidden as e:
            logging.error(
                f"ROLES ERROR: Permission error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise PermissionError(
                message=f"I don't have permission to manage roles: {e}"
            ) from e
        except discord.HTTPException as e:
            logging.error(
                f"ROLES ERROR: Discord API error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(message=f"Failed to modify roles: {e}") from e
        except Exception as e:
            logging.error(
                f"ROLES ERROR: Unexpected error for role {role.id if role else 'unknown'} by user {interaction.user.id}: {e}"
            )
            raise ExternalServiceError(
                message=f"Unexpected error while toggling role: {e}"
            ) from e

    @commands.Cog.listener()
    async def on_member_update(
        self, before: discord.Member, after: discord.Member
    ) -> None:
        """Event handler for when a member's roles are updated.

        This listener detects when a member gains a special role and sends a themed
        announcement message to the inn general channel.
        """
        list_of_ids = [
            config.special_role_ids["acid_jars"],
            config.special_role_ids["acid_flies"],
            config.special_role_ids["frying_pans"],
            config.special_role_ids["enchanted_soup"],
            config.special_role_ids["barefoot_clients"],
        ]
        gained = set(after.roles) - set(before.roles)
        if gained:
            gained = gained.pop()
            if gained.id in list_of_ids:
                channel = self.bot.get_channel(config.inn_general_channel_id)
                if gained.id == config.special_role_ids["acid_jars"]:
                    embed = discord.Embed(
                        title="Hey be careful over there!",
                        description=f"Those {gained.mention} will melt your hands off {after.mention}!",
                    )
                elif gained.id == config.special_role_ids["acid_flies"]:
                    embed = discord.Embed(
                        title="Make some room at the tables!",
                        description=f"{after.mention} just ordered a bowl of {gained.mention}!",
                    )
                elif gained.id == config.special_role_ids["frying_pans"]:
                    embed = discord.Embed(
                        title="Someone ordered a frying pan!",
                        description=f"Hope {after.mention} can dodge!",
                    )
                elif gained.id == config.special_role_ids["enchanted_soup"]:
                    embed = discord.Embed(
                        title="Hey get down from there Mrsha!",
                        description=f"Looks like {after.mention} will have to order a new serving of {gained.mention} because Mrsha just ate theirs!",
                    )
                elif gained.id == config.special_role_ids["barefoot_clients"]:
                    embed = discord.Embed(
                        title="Make way!",
                        description=f"{gained.mention} {after.mention} coming through!",
                    )
                else:
                    embed = discord.Embed(
                        title="Make some room in the inn!",
                        description=f"{after.mention} just joined the ranks of {gained.mention}!",
                    )
                embed.set_thumbnail(url=after.display_avatar.url)
                await channel.send(embed=embed, content=f"{after.mention}")


async def setup(bot: commands.Bot) -> None:
    """Set up the Roles cog."""
    await bot.add_cog(Roles(bot))
