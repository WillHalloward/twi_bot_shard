# Twi Bot Shard API Documentation

This document provides comprehensive documentation for all commands and features of the Twi Bot Shard, including usage examples and troubleshooting guides.

## Table of Contents

1. [Command Overview](#command-overview)
2. [Command Categories](#command-categories)
   - [Moderation Commands](#moderation-commands)
   - [Utility Commands](#utility-commands)
   - [Configuration Commands](#configuration-commands)
   - [Creator Link Commands](#creator-link-commands)
   - [Gallery Commands](#gallery-commands)
   - [Statistics Commands](#statistics-commands)
   - [Other Commands](#other-commands)
3. [Common Operations](#common-operations)
4. [Troubleshooting](#troubleshooting)
5. [API Integration](#api-integration)

## Command Overview

Twi Bot Shard supports both traditional prefix commands and Discord's slash commands. The default prefix for traditional commands is `!`, but this can be configured per server.

### Command Syntax

Commands are documented using the following format:

```
/command <required_parameter> [optional_parameter]
```

- Parameters in `<angle brackets>` are required
- Parameters in `[square brackets]` are optional
- Parameters with `=default` have a default value if not specified

## Command Categories

### Moderation Commands

#### User Management

##### `/ban <user> [reason] [delete_days=1]`

Bans a user from the server.

**Parameters:**
- `user`: The user to ban (mention, ID, or name)
- `reason`: The reason for the ban (optional)
- `delete_days`: Number of days of messages to delete (default: 1)

**Examples:**
```
/ban @Username Spamming in channels
/ban 123456789012345678 Inappropriate behavior 7
```

**Permissions Required:** Ban Members

---

##### `/kick <user> [reason]`

Kicks a user from the server.

**Parameters:**
- `user`: The user to kick (mention, ID, or name)
- `reason`: The reason for the kick (optional)

**Examples:**
```
/kick @Username Disruptive behavior
```

**Permissions Required:** Kick Members

---

##### `/mute <user> <duration> [reason]`

Temporarily mutes a user in the server.

**Parameters:**
- `user`: The user to mute (mention, ID, or name)
- `duration`: The duration of the mute (e.g., 10m, 1h, 1d)
- `reason`: The reason for the mute (optional)

**Examples:**
```
/mute @Username 30m Excessive spam
/mute 123456789012345678 2h Inappropriate language
```

**Permissions Required:** Manage Roles

---

##### `/unmute <user> [reason]`

Unmutes a previously muted user.

**Parameters:**
- `user`: The user to unmute (mention, ID, or name)
- `reason`: The reason for the unmute (optional)

**Examples:**
```
/unmute @Username Time served
```

**Permissions Required:** Manage Roles

---

#### Message Management

##### `/purge <count> [user]`

Deletes a specified number of messages from a channel.

**Parameters:**
- `count`: The number of messages to delete (1-100)
- `user`: Only delete messages from this user (optional)

**Examples:**
```
/purge 50
/purge 20 @Username
```

**Permissions Required:** Manage Messages

---

##### `/slowmode <seconds>`

Sets the slowmode delay for the current channel.

**Parameters:**
- `seconds`: The slowmode delay in seconds (0-21600)

**Examples:**
```
/slowmode 5
/slowmode 0  # Disables slowmode
```

**Permissions Required:** Manage Channels

---

### Utility Commands

#### `/help [command]`

Displays help information for commands.

**Parameters:**
- `command`: The command to get help for (optional)

**Examples:**
```
/help
/help ban
```

---

#### `/ping`

Checks the bot's response time and API latency.

**Examples:**
```
/ping
```

---

#### `/userinfo [user]`

Displays information about a user.

**Parameters:**
- `user`: The user to get information about (default: yourself)

**Examples:**
```
/userinfo
/userinfo @Username
```

---

#### `/serverinfo`

Displays information about the current server.

**Examples:**
```
/serverinfo
```

---

### Configuration Commands

#### `/settings view`

Displays the current bot settings for the server.

**Examples:**
```
/settings view
```

**Permissions Required:** Manage Server

---

#### `/settings prefix <new_prefix>`

Changes the command prefix for the server.

**Parameters:**
- `new_prefix`: The new prefix to use for commands

**Examples:**
```
/settings prefix !
/settings prefix ?
```

**Permissions Required:** Manage Server

---

#### `/settings logs <channel>`

Sets the channel for logging bot actions.

**Parameters:**
- `channel`: The channel to send logs to

**Examples:**
```
/settings logs #bot-logs
```

**Permissions Required:** Manage Server

---

### Creator Link Commands

#### `/link add <platform> <username> <url>`

Adds a creator link to the database.

**Parameters:**
- `platform`: The platform (e.g., Twitter, DeviantArt)
- `username`: The creator's username
- `url`: The URL to their profile or content

**Examples:**
```
/link add Twitter artist_name https://twitter.com/artist_name
```

**Permissions Required:** Manage Messages or configured role

---

#### `/link remove <platform> <username>`

Removes a creator link from the database.

**Parameters:**
- `platform`: The platform
- `username`: The creator's username

**Examples:**
```
/link remove Twitter artist_name
```

**Permissions Required:** Manage Messages or configured role

---

#### `/link search <query>`

Searches for creator links in the database.

**Parameters:**
- `query`: The search query

**Examples:**
```
/link search artist_name
```

---

### Gallery Commands

#### `/gallery add <title> <url> [description]`

Adds an image to the gallery.

**Parameters:**
- `title`: The title of the image
- `url`: The URL of the image
- `description`: A description of the image (optional)

**Examples:**
```
/gallery add "Sunset Artwork" https://example.com/image.png "A beautiful sunset"
```

**Permissions Required:** Manage Messages or configured role

---

#### `/gallery remove <id>`

Removes an image from the gallery.

**Parameters:**
- `id`: The ID of the image to remove

**Examples:**
```
/gallery remove 123
```

**Permissions Required:** Manage Messages or configured role

---

#### `/gallery search <query>`

Searches for images in the gallery.

**Parameters:**
- `query`: The search query

**Examples:**
```
/gallery search sunset
```

---

### Statistics Commands

#### `/stats server`

Displays server activity statistics.

**Examples:**
```
/stats server
```

---

#### `/stats user [user]`

Displays user activity statistics.

**Parameters:**
- `user`: The user to get statistics for (default: yourself)

**Examples:**
```
/stats user
/stats user @Username
```

---

#### `/stats commands`

Displays command usage statistics.

**Examples:**
```
/stats commands
```

**Permissions Required:** Manage Server

---

### Other Commands

#### `/report <message_link> <reason>`

Reports a message to the moderators.

**Parameters:**
- `message_link`: The link to the message
- `reason`: The reason for the report

**Examples:**
```
/report https://discord.com/channels/123/456/789 Inappropriate content
```

---

#### `/summarize <message_count>`

Summarizes recent messages in the channel.

**Parameters:**
- `message_count`: The number of messages to summarize (5-100)

**Examples:**
```
/summarize 50
```

---

## Common Operations

### Setting Up the Bot

1. **Invite the bot to your server**:
   - Use the OAuth2 URL provided by the bot owner
   - Ensure the bot has the necessary permissions

2. **Configure basic settings**:
   ```
   /settings prefix !
   /settings logs #bot-logs
   ```

3. **Set up role permissions**:
   - Create roles for bot usage if needed
   - Configure which roles can use which commands

### Moderating Your Server

1. **Handling spam**:
   - Use `/mute @User 10m Spamming` to temporarily mute a user
   - Use `/purge 50` to clean up spam messages

2. **Dealing with rule violations**:
   - Use `/warn @User Breaking rule #3` to issue a warning
   - Use `/kick @User Continued rule violations` for repeated offenses
   - Use `/ban @User Severe rule violation` for serious offenses

### Managing Creator Links

1. **Adding multiple links for a creator**:
   ```
   /link add Twitter artist_name https://twitter.com/artist_name
   /link add DeviantArt artist_name https://deviantart.com/artist_name
   ```

2. **Finding creator links**:
   ```
   /link search artist
   ```

### Working with the Gallery

1. **Adding images to the gallery**:
   ```
   /gallery add "Artwork Title" https://example.com/image.png "Description"
   ```

2. **Creating a gallery showcase**:
   ```
   /gallery showcase 5 newest
   ```

## Troubleshooting

### Common Issues

#### Bot Not Responding to Commands

1. **Check the bot's status**:
   - Ensure the bot is online and in your server
   - Check if the bot has the necessary permissions

2. **Verify command syntax**:
   - Make sure you're using the correct prefix
   - Check the command syntax with `/help [command]`

3. **Check channel permissions**:
   - Ensure the bot can read and send messages in the channel

#### Permission Errors

1. **Bot missing permissions**:
   - Check if the bot has the required permissions for the command
   - Try moving the bot's role higher in the role hierarchy

2. **User missing permissions**:
   - Verify that you have the necessary permissions for the command
   - Ask a server administrator for assistance

#### Database-Related Issues

1. **Link or gallery commands not working**:
   - The database might be experiencing issues
   - Try again later or contact the bot owner

2. **Slow response times**:
   - High server load might cause delays
   - Complex queries might take longer to process

### Error Messages

| Error Message | Possible Cause | Solution |
|---------------|----------------|----------|
| "Command on cooldown" | You're using the command too frequently | Wait for the cooldown to expire |
| "Missing permissions" | You or the bot lacks required permissions | Check permissions and role hierarchy |
| "Invalid argument" | Incorrect command syntax | Check `/help [command]` for proper usage |
| "Database error" | Issue with the database connection | Try again later or report to bot owner |

### Getting Help

If you encounter issues not covered in this documentation:

1. Use `/help` to check command syntax
2. Ask in the support server (if available)
3. Contact the bot owner or administrators

## API Integration

### Webhook Support

Twi Bot Shard supports webhooks for certain events:

1. **Moderation actions**:
   - Configure with `/settings webhook moderation #channel`
   - Receives notifications for bans, kicks, mutes, etc.

2. **New content**:
   - Configure with `/settings webhook content #channel`
   - Receives notifications for new gallery entries and creator links

### Custom Commands

Server administrators can create custom commands:

```
/custom add command_name Response text
```

### External Integrations

The bot supports integration with:

1. **Twitter** - For fetching tweets and monitoring accounts
2. **DeviantArt** - For gallery integration
3. **AO3** - For story updates and notifications

For more information on setting up these integrations, contact the bot owner or administrators.