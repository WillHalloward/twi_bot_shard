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

## Command Permission Requirements

Below is a list of commands and their required permission levels:

### Gallery Commands
- `gallery`: USER level
- `gallery add`: USER level
- `gallery remove`: USER level (own submissions) or ADMIN level (any submission)
- `gallery search`: USER level

### Links & Tags Commands
- `link`: USER level
- `link add`: USER level
- `link remove`: USER level (own submissions) or ADMIN level (any submission)
- `link edit`: USER level (own submissions) or ADMIN level (any submission)
- `tag`: USER level
- `tag add`: MODERATOR level
- `tag remove`: MODERATOR level

### Moderation Commands
- `ban`: MODERATOR level (requires `ban_members` permission)
- `kick`: MODERATOR level (requires `kick_members` permission)
- `mute`: MODERATOR level
- `unmute`: MODERATOR level
- `purge`: MODERATOR level (requires `manage_messages` permission)
- `warn`: MODERATOR level
- `warnings`: MODERATOR level

### Administrative Commands
- `set_admin_role`: ADMIN level (requires `manage_permissions` permission)
- `get_admin_role`: USER level
- `set_permission_level`: ADMIN level (requires `manage_permissions` permission)
- `set_permission`: ADMIN level (requires `manage_permissions` permission)

### Owner Commands
- `restart`: OWNER level (requires `manage_bot` permission)
- `update`: OWNER level (requires `manage_bot` permission)
- `exec`: OWNER level (requires `manage_bot` permission)
- `load`: OWNER level (requires `manage_bot` permission)
- `unload`: OWNER level (requires `manage_bot` permission)
- `reload`: OWNER level (requires `manage_bot` permission)

## Managing Permissions

### Setting Permission Levels

Server administrators can set permission levels for roles using the following command:

```
/set_permission_level role:<role> level:<level>
```

Where `<role>` is the role to set the permission level for, and `<level>` is one of: `USER`, `MODERATOR`, `ADMIN`, or a numeric value.

### Setting Specific Permissions

Server administrators can grant or deny specific permissions to roles using the following command:

```
/set_permission role:<role> permission:<permission> value:<true/false>
```

Where `<role>` is the role to set the permission for, `<permission>` is the permission name, and `<value>` is either `true` to grant the permission or `false` to deny it.

### User-Specific Permissions

In addition to role-based permissions, the bot supports user-specific permission levels and overrides. These can be set using the following commands:

```
/set_user_permission_level user:<user> level:<level>
/set_user_permission user:<user> permission:<permission> value:<true/false>
```

User-specific permissions take precedence over role-based permissions.

## Default Permissions

By default, the bot assigns the following permission levels:

- Server owner: ADMIN level
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