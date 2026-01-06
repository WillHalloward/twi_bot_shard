# Permission System Documentation

## Overview

The Twi Bot Shard uses a comprehensive role-based access control system to manage permissions for commands and features. This document provides information about the permission system, including permission levels, specific permissions, and how to manage permissions.

## Permission Levels

The bot uses the following permission levels, in ascending order of authority:

| Level | Name | Description |
|-------|------|-------------|
| 0 | NONE | No permissions |
| 10 | USER | Basic user permissions |
| 50 | MODERATOR | Moderator permissions |
| 80 | ADMIN | Administrator permissions |
| 100 | OWNER | Bot owner permissions |

Each level includes all permissions from lower levels.

## Specific Permissions

The bot defines the following specific permissions:

### Basic Permissions (USER level)
- `view_commands`: Ability to see commands in help listings
- `use_basic_commands`: Ability to use basic, non-administrative commands

### Moderation Permissions (MODERATOR level)
- `manage_messages`: Ability to delete, pin, and manage messages
- `manage_threads`: Ability to create and manage threads
- `manage_roles`: Ability to manage roles (except administrative roles)
- `kick_members`: Ability to kick members from the server
- `ban_members`: Ability to ban members from the server

### Administrative Permissions (ADMIN level)
- `manage_guild`: Ability to manage server settings
- `manage_channels`: Ability to create and manage channels
- `manage_webhooks`: Ability to create and manage webhooks
- `manage_permissions`: Ability to manage the permission system

### Bot Owner Permissions (OWNER level)
- `manage_bot`: Ability to manage the bot itself (restart, update, etc.)

## Managing Permissions

### Admin Role Configuration

Server administrators can configure an admin role using the following commands:

#### Set Admin Role

```
/set_admin_role role:<role>
```

Sets the admin role for the server. Users with this role will be granted ADMIN level permissions. Requires `manage_messages` Discord permission.

#### Get Admin Role

```
/get_admin_role
```

Shows the currently configured admin role for the server. Available to all users.

## Default Permissions

By default, the bot assigns the following permission levels:

- Bot owner: OWNER level
- Users with the admin role (set via `/set_admin_role`): ADMIN level
- Users with the "Ban Members" Discord permission: MODERATOR level
- All other users: USER level

## Technical Implementation

The permission system is implemented in the `utils/permissions.py` file. It uses a database to store permission levels and overrides for roles and users.

For developers, the following decorators are available for checking permissions in commands:

```python
@has_permission(Permission.PERMISSION_NAME)
@has_permission_level(PermissionLevel.LEVEL_NAME)
```

These decorators can be used with both traditional commands and application commands (slash commands).

### Example Usage

```python
from utils.permissions import has_permission, has_permission_level, Permission, PermissionLevel

# Check for a specific permission
@has_permission(Permission.MANAGE_MESSAGES)
async def delete_message(self, ctx):
    # Only users with manage_messages permission can use this
    pass

# Check for a permission level
@has_permission_level(PermissionLevel.ADMIN)
async def admin_only_command(self, ctx):
    # Only admins and higher can use this
    pass
```

### Permission Manager Methods

The `PermissionManager` class provides the following methods for programmatic permission management:

- `get_user_permission_level(guild_id, user_id, user_roles)` - Get a user's permission level
- `has_permission(guild_id, user_id, permission, user_roles)` - Check if a user has a specific permission
- `set_role_permission_level(guild_id, role_id, level)` - Set permission level for a role
- `set_user_permission_level(guild_id, user_id, level)` - Set permission level for a user
- `set_permission_override(guild_id, target_id, permission, value, is_role)` - Set specific permission overrides

These methods are available for cogs and other bot components but are not directly exposed as user-facing commands.
