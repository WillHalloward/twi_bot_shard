# Permission System Documentation

## Overview

The Twi Bot Shard uses a **simplified permission system** that leverages Discord's
native guild permissions, with a bot-owner override and a per-server configurable
admin role. There is no custom role-based access-control engine, permission-level
enum, or database-backed permission store — checks are evaluated dynamically at
command time.

The implementation lives in `utils/permissions.py`. Per-server admin-role
configuration is handled by the `Settings` cog (`cogs/settings.py`).

## Permission Tiers

The bot recognises three effective tiers, evaluated in order:

| Tier | Who qualifies |
|------|---------------|
| **Owner** | The single bot owner (`config.bot_owner_id`). Always passes every check. |
| **Admin** | Bot owner, **or** a member with Discord's `administrator` permission, **or** a member with the server's configured admin role. |
| **Moderator** | Bot owner, anyone who is Admin, **or** a member with Discord's `ban_members` permission. |

There are no numeric permission levels and no named fine-grained permissions
(e.g. `manage_messages`, `view_commands`) — those do not exist in the code.

## Managing the Admin Role

Server administrators configure the admin role through the `Settings` cog's
slash commands:

### Set Admin Role

```
/set_admin_role role:<role>
```

Sets the admin role for the server. Members with this role are treated as Admin
by the bot.

### Get Admin Role

```
/get_admin_role
```

Shows the currently configured admin role for the server.

The configured role ID is persisted via `ServerSettingsRepository`
(`utils/repositories/server_settings_repository.py`) and read back by
`get_admin_role_id(guild_id)`.

## Technical Implementation

The core checks in `utils/permissions.py` are:

```python
is_bot_owner(user_id) -> bool                              # owner override
async is_admin(bot, guild_id, user_id, user_roles=None)    # owner / admin role / Discord administrator
async is_moderator(bot, guild_id, user_id)                 # owner / admin / Discord ban_members
async is_bot_channel(ctx_or_interaction)                   # restrict to config.bot_channel_id
```

### Check Functions and Decorators

The check functions accept **either** a `commands.Context` (prefix commands) or a
`discord.Interaction` (slash commands), and raise `PermissionError` /
`OwnerOnlyError` from `utils/exceptions.py` when the user lacks permission.

| Check | Prefix-command form (`@commands.check`) | Slash-command form (`@app_commands.check`) |
|-------|-----------------------------------------|--------------------------------------------|
| Admin or owner | `admin_or_me_check_wrapper` | `app_admin_or_me_check` |
| Moderator or owner | `moderator_check_wrapper` | `app_moderator_check` |
| Bot channel only | `is_bot_channel_wrapper` | `app_is_bot_channel` |
| Owner only | `owner_only` (works for both) | `owner_only` (works for both) |

### Example Usage

```python
from discord import app_commands
from discord.ext import commands

from utils.permissions import (
    app_admin_or_me_check,
    app_moderator_check,
    owner_only,
)

# Slash command restricted to admins (or the bot owner)
@app_commands.command()
@app_commands.check(app_admin_or_me_check)
async def admin_only_slash(self, interaction):
    ...

# Slash command restricted to moderators (or admins / owner)
@app_commands.command()
@app_commands.check(app_moderator_check)
async def mod_only_slash(self, interaction):
    ...

# Owner-only command (works for both prefix and slash commands)
@commands.command()
@owner_only
async def owner_only_command(self, ctx):
    ...
```

When a check fails it raises `PermissionError` (or `OwnerOnlyError`), which the
error-handling decorators turn into a friendly "you don't have permission"
response — see the [Error Handling guide](error-handling.md).

### setup_permissions

`setup_permissions(bot)` exists for compatibility but is a **no-op**: there is no
permission state to initialise because checks are evaluated dynamically against
Discord's native permissions.
