# Twi Bot Shard User Manual

Welcome to the Twi Bot Shard User Manual! This guide will help you understand how to use and configure the bot for your Discord server.

## Table of Contents

1. [Introduction](#introduction)
2. [Getting Started](#getting-started)
   - [Inviting the Bot](#inviting-the-bot)
   - [Initial Setup](#initial-setup)
   - [Permission Configuration](#permission-configuration)
3. [Basic Commands](#basic-commands)
   - [Help Commands](#help-commands)
   - [Information Commands](#information-commands)
   - [Configuration Commands](#configuration-commands)
4. [Moderation Features](#moderation-features)
   - [User Management](#user-management)
   - [Message Management](#message-management)
   - [Role Management](#role-management)
5. [Content Management](#content-management)
   - [Gallery System](#gallery-system)
   - [Creator Links](#creator-links)
6. [Utility Features](#utility-features)
   - [Statistics Tracking](#statistics-tracking)
   - [Summarization](#summarization)
   - [Search Commands](#search-commands)
7. [Advanced Configuration](#advanced-configuration)
   - [Custom Commands](#custom-commands)
   - [Automated Responses](#automated-responses)
   - [Scheduled Tasks](#scheduled-tasks)
8. [Troubleshooting](#troubleshooting)
   - [Common Issues](#common-issues)
   - [Error Messages](#error-messages)
   - [Getting Help](#getting-help)
9. [FAQ](#faq)
10. [Command Reference](#command-reference)

## Introduction

Twi Bot Shard is a multipurpose Discord bot designed to help server administrators and moderators manage their communities effectively. It provides moderation tools, content management features, utility commands, and more.

### Key Features

- **Moderation Tools**: Ban, kick, mute, and warn users; manage messages and channels
- **Content Management**: Gallery system for images, creator link management
- **Utility Commands**: Server and user statistics, message summarization, search functionality
- **Customization**: Custom commands, automated responses, and scheduled tasks

## Getting Started

### Inviting the Bot

To add Twi Bot Shard to your Discord server:

1. Click on [this invite link](https://discord.com/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=8&scope=bot%20applications.commands)
2. Select your server from the dropdown menu
3. Review the requested permissions
4. Click "Authorize"

### Initial Setup

After adding the bot to your server, you should configure it:

1. Set the command prefix (default is `!`):
   ```
   /settings prefix !
   ```

2. Set up a logging channel to track bot actions:
   ```
   /settings logs #bot-logs
   ```

3. Configure moderation settings:
   ```
   /settings moderation enable_warnings=true auto_mute_after=3
   ```

### Permission Configuration

Twi Bot Shard uses Discord's role-based permission system. Here's how to set it up:

1. **Bot Role**: Ensure the bot's role is positioned above any roles it needs to manage
2. **Command Permissions**: You can restrict commands to specific roles:
   ```
   /settings permissions command=ban roles=@Moderator,@Admin
   ```
3. **Feature Permissions**: You can also restrict features:
   ```
   /settings permissions feature=gallery roles=@ContentCreator,@Moderator
   ```

## Basic Commands

### Help Commands

- `/help`: Shows the interactive help system with categories and commands
- `/help <command>`: Shows detailed help for a specific command
- `/help category <category>`: Shows commands in a specific category

#### Using the Interactive Help System

The bot features an intuitive interactive help system that makes it easy to discover and learn about commands:

1. Type `/help` to open the interactive help menu
2. You'll see a dropdown menu with command categories (Moderation, Utility, Configuration, etc.)
3. Select a category to view all commands in that category
4. Select a specific command to view detailed information including:
   - Command syntax
   - Full description
   - Usage examples
   - Required permissions (if any)
5. Use the "Back to Category" button to return to the category view

This interactive system makes it easy to explore the bot's capabilities without needing to remember specific command names or syntax.

### Information Commands

- `/info`: Shows information about the bot
- `/serverinfo`: Shows information about the current server
- `/userinfo [user]`: Shows information about a user

### Configuration Commands

- `/settings view`: Shows current bot settings
- `/settings prefix <prefix>`: Changes the command prefix
- `/settings logs <channel>`: Sets the logging channel
- `/settings moderation <options>`: Configures moderation settings

## Moderation Features

### User Management

#### Banning Users

```
/ban <user> [reason] [delete_days=1]
```

Bans a user from the server and optionally deletes their recent messages.

**Examples:**
- `/ban @Username Spamming in channels`
- `/ban 123456789012345678 Inappropriate behavior 7`

#### Kicking Users

```
/kick <user> [reason]
```

Removes a user from the server, but they can rejoin with an invite.

**Examples:**
- `/kick @Username Disruptive behavior`

#### Muting Users

```
/mute <user> <duration> [reason]
```

Temporarily prevents a user from sending messages or joining voice channels.

**Examples:**
- `/mute @Username 30m Excessive spam`
- `/mute 123456789012345678 2h Inappropriate language`

#### Warning Users

```
/warn <user> <reason>
```

Issues a formal warning to a user, which is logged in the database.

**Examples:**
- `/warn @Username Breaking rule #3`

#### Viewing User History

```
/history <user>
```

Shows a user's moderation history (warnings, mutes, kicks, bans).

**Examples:**
- `/history @Username`

### Message Management

#### Purging Messages

```
/purge <count> [user]
```

Deletes a specified number of messages from a channel.

**Examples:**
- `/purge 50` - Deletes the last 50 messages
- `/purge 20 @Username` - Deletes up to 20 messages from the specified user

#### Slowmode

```
/slowmode <seconds>
```

Sets the slowmode delay for the current channel.

**Examples:**
- `/slowmode 5` - Users can only send one message every 5 seconds
- `/slowmode 0` - Disables slowmode

### Role Management

#### Adding Roles

```
/role add <user> <role>
```

Adds a role to a user.

**Examples:**
- `/role add @Username @Moderator`

#### Removing Roles

```
/role remove <user> <role>
```

Removes a role from a user.

**Examples:**
- `/role remove @Username @Moderator`

## Content Management

### Gallery System

The gallery system allows you to store and organize images.

#### Adding Images

```
/gallery add <title> <url> [description]
```

Adds an image to the gallery.

**Examples:**
- `/gallery add "Sunset Artwork" https://example.com/image.png "A beautiful sunset"`

#### Viewing Images

```
/gallery view <id>
```

Displays a specific image from the gallery.

**Examples:**
- `/gallery view 123`

#### Searching Images

```
/gallery search <query>
```

Searches for images in the gallery.

**Examples:**
- `/gallery search sunset`

#### Removing Images

```
/gallery remove <id>
```

Removes an image from the gallery.

**Examples:**
- `/gallery remove 123`

### Creator Links

The creator links system helps you manage links to creator profiles.

#### Adding Links

```
/link add <platform> <username> <url>
```

Adds a creator link to the database.

**Examples:**
- `/link add Twitter artist_name https://twitter.com/artist_name`

#### Viewing Links

```
/link view <platform> <username>
```

Displays a specific creator link.

**Examples:**
- `/link view Twitter artist_name`

#### Searching Links

```
/link search <query>
```

Searches for creator links in the database.

**Examples:**
- `/link search artist_name`

#### Removing Links

```
/link remove <platform> <username>
```

Removes a creator link from the database.

**Examples:**
- `/link remove Twitter artist_name`

## Utility Features

### Statistics Tracking

#### Server Statistics

```
/stats server
```

Displays server activity statistics.

**Examples:**
- `/stats server`

#### User Statistics

```
/stats user [user]
```

Displays user activity statistics.

**Examples:**
- `/stats user`
- `/stats user @Username`

#### Command Statistics

```
/stats commands
```

Displays command usage statistics.

**Examples:**
- `/stats commands`

### Summarization

```
/summarize <message_count>
```

Summarizes recent messages in the channel.

**Examples:**
- `/summarize 50` - Summarizes the last 50 messages

### Search Commands

```
/search <query>
```

Searches for messages containing the query.

**Examples:**
- `/search announcement`

## Advanced Configuration

### Custom Commands

You can create custom commands that respond with predefined text.

#### Creating Custom Commands

```
/custom add <name> <response>
```

Creates a new custom command.

**Examples:**
- `/custom add rules Please read the rules in #rules`

#### Using Custom Commands

```
!<command_name>
```

Executes a custom command.

**Examples:**
- `!rules`

#### Removing Custom Commands

```
/custom remove <name>
```

Removes a custom command.

**Examples:**
- `/custom remove rules`

### Automated Responses

You can set up the bot to automatically respond to certain triggers.

#### Adding Auto Responses

```
/autoresponse add <trigger> <response>
```

Creates a new automated response.

**Examples:**
- `/autoresponse add "welcome" "Welcome to the server!"`

#### Removing Auto Responses

```
/autoresponse remove <trigger>
```

Removes an automated response.

**Examples:**
- `/autoresponse remove "welcome"`

### Scheduled Tasks

You can schedule recurring tasks like announcements.

#### Creating Scheduled Tasks

```
/schedule add <name> <cron> <command>
```

Creates a new scheduled task.

**Examples:**
- `/schedule add daily_reminder "0 12 * * *" "say #general Don't forget to drink water!"`

#### Removing Scheduled Tasks

```
/schedule remove <name>
```

Removes a scheduled task.

**Examples:**
- `/schedule remove daily_reminder`

## Troubleshooting

### Common Issues

#### Bot Not Responding

If the bot isn't responding to commands:

1. Check if the bot is online
2. Ensure you're using the correct prefix
3. Check if the bot has the necessary permissions
4. Verify that you have permission to use the command

#### Command Errors

If you're getting errors when using commands:

1. Check the command syntax with `/help <command>`
2. Ensure all required parameters are provided
3. Verify that the bot has the necessary permissions

### Error Messages

Here are some common error messages and what they mean:

- **"You don't have permission to use this command"**: You lack the required permissions
- **"I don't have permission to do that"**: The bot lacks the required permissions
- **"Command on cooldown"**: You're using the command too frequently
- **"Invalid argument"**: One of your command arguments is incorrect

### Getting Help

If you're still having issues:

1. Check the [FAQ](#faq) section below
2. Join the support server: [Discord Invite Link](https://discord.gg/support-server)
3. Contact the bot developer: `@developer_username`

## FAQ

### General Questions

#### How do I change the bot's prefix?

Use the `/settings prefix` command:
```
/settings prefix !
```

#### Can I use the bot in multiple servers?

Yes, you can invite the bot to as many servers as you want.

#### Is the bot free to use?

Yes, the bot is free to use with all its basic features. Some advanced features may require a premium subscription.

#### How do I get help with using the bot?

There are several ways to get help:
1. Use the interactive help system by typing `/help`
2. Check this user manual for detailed information
3. Join the support server for direct assistance
4. Contact the bot developer for specific issues

#### Can I customize the bot's responses?

Yes, you can create custom commands and automated responses. See the [Advanced Configuration](#advanced-configuration) section for details.

#### How do I report bugs or suggest features?

You can report bugs or suggest features by:
1. Using the `/report` command in Discord
2. Opening an issue on the GitHub repository
3. Joining the support server and posting in the appropriate channel

### Moderation Questions

#### How do I set up auto-moderation?

Use the `/settings automod` command:
```
/settings automod enable=true filter_spam=true filter_invites=true
```

#### Can the bot automatically assign roles to new members?

Yes, use the `/settings autorole` command:
```
/settings autorole @Member
```

#### How do I view a user's moderation history?

Use the `/history` command followed by the username:
```
/history @Username
```

#### Can I set custom punishment levels for different infractions?

Yes, use the `/settings punishments` command:
```
/settings punishments warning=1 mute=3 kick=5 ban=7
```

#### How do I reset a command's cooldown?

If you have the appropriate permissions, use the `/reset` command:
```
/reset command_name
```

### Content Management Questions

#### How many images can I store in the gallery?

The gallery can store up to 1,000 images per server.

#### Can I categorize images in the gallery?

Yes, you can add tags to images when adding them:
```
/gallery add "Title" https://example.com/image.png "Description" tags=art,landscape
```

#### How do I find all links for a specific creator?

Use the `/link search` command with the creator's name:
```
/link search creator_name
```

#### Can users submit images to the gallery?

Yes, if they have the appropriate permissions. You can configure which roles can add images using:
```
/settings permissions feature=gallery roles=@ContentCreator,@Trusted
```

### Interactive Help Questions

#### How do I navigate the interactive help system?

1. Type `/help` to open the interactive help menu
2. Use the dropdown menu to select a command category
3. Select a specific command to view detailed information
4. Use the "Back to Category" button to return to the category list

#### Can I search for specific commands?

Yes, you can use `/help command_name` to directly view information about a specific command.

#### Why are some commands not showing up in the help system?

Commands may not appear in the help system if:
1. You don't have permission to use them
2. They're disabled in your server
3. They're hidden administrative commands

### Technical Questions

#### What permissions does the bot need?

The bot needs various permissions depending on the features you use. At minimum, it needs:
- Read Messages/View Channels
- Send Messages
- Embed Links
- Attach Files
- Read Message History

For moderation features, it also needs:
- Kick Members
- Ban Members
- Manage Messages
- Manage Roles

#### Can I host the bot myself?

Yes, the bot is open-source and can be self-hosted. See the [developer documentation](developer_onboarding.md) for details.

#### How does the bot store data?

The bot uses a PostgreSQL database to store all persistent data, including:
- User moderation records
- Gallery images and metadata
- Creator links
- Server settings
- Command usage statistics

#### Is my data secure?

Yes, the bot uses industry-standard security practices:
- All database connections use SSL encryption
- Sensitive data is stored securely
- Regular backups are performed
- Access to data is strictly controlled

## Command Reference

For a complete list of commands and their usage, see the [API Documentation](api_documentation.md).
