# Features - Twi Bot Shard (Cognita)

This document provides a comprehensive list of features and commands available in the Twi Bot Shard (Cognita).

## Command Categories

- [Gallery & Mementos](#gallery--mementos)
- [Links & Tags](#links--tags)
- [Moderation](#moderation)
- [Utility Commands](#utility-commands)
- [Patreon Poll](#patreon-poll)
- [The Wandering Inn](#the-wandering-inn)
- [Creator Links](#creator-links)
- [Reporting](#reporting)
- [Innktober](#innktober)
- [Summarization](#summarization)
- [Statistics](#statistics)
- [Owner Commands](#owner-commands)

## Gallery & Mementos

Commands for managing image galleries.

### Gallery Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!gallery` | Adds an image to the gallery channel | `!gallery [image attachment]` | Everyone |
| `!setGallery` | Sets the channel where gallery images are posted | `!setGallery #channel` | Admin |

### Mementos Commands

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!mementos` | Adds an image to the mementos channel | `!mementos [image attachment]` | Everyone |
| `!setMementos` | Sets the channel where mementos are posted | `!setMementos #channel` | Admin |

## Links & Tags

Commands for managing links and tags.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!addlink` | Adds a link with the given name to the given URL and tag | `!addlink name url tag` | Mod |
| `!delink` | Deletes a link with the given name | `!delink name` | Mod |
| `!link` | Posts the link with the given name | `!link name` | Everyone |
| `!links` | View all links | `!links` | Everyone |
| `!tag` | View all links that have a certain tag | `!tag tagname` | Everyone |
| `!tags` | See all available tags | `!tags` | Everyone |

## Moderation

Commands for server moderation.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!reset` | Resets the cooldown of a command | `!reset command_name @user` | Mod |
| `!backup` | Backups the channel | `!backup` | Mod |

## Utility Commands

General utility commands.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!avatar` | Posts the full version of an avatar | `!avatar @user` | Everyone |
| `!info` | Gives the account information of a user | `!info @user` | Everyone |
| `!ping` | Gives the latency of the bot | `!ping` | Everyone |
| `!say` | Makes Cognita repeat whatever was said | `!say message` | Mod |
| `!saychannel` | Makes Cognita repeat whatever was said in a specific channel | `!saychannel #channel message` | Mod |

## Patreon Poll

Commands for interacting with Patreon polls.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!findpoll` | Searches poll questions for a given query | `!findpoll query` | Everyone |
| `!getpoll` | Fetches the latest poll from Patreon | `!getpoll` | Mod |
| `!poll` | Posts the latest poll or a specific poll | `!poll [number]` | Everyone |

## The Wandering Inn

Commands specific to The Wandering Inn.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!coloredtext` | List of all the different colored texts in TWI | `!coloredtext` | Everyone |
| `!connectdiscord` | Information for Patreons on how to connect their Patreon account | `!connectdiscord` | Everyone |
| `!invistext` | Gives a list of all the invisible text in TWI | `!invistext` | Everyone |
| `!password` | Information for Patreons on how to get the chapter password | `!password` | Everyone |
| `!wiki` | Searches The Wandering Inn wiki for a matching article | `!wiki query` | Everyone |

## Creator Links

Commands for managing creator links.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!addcreator` | Adds a creator link | `!addcreator name url` | Mod |
| `!removecreator` | Removes a creator link | `!removecreator name` | Mod |
| `!creator` | Shows a specific creator link | `!creator name` | Everyone |
| `!creators` | Lists all creator links | `!creators` | Everyone |

## Reporting

Commands for reporting issues.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!report` | Reports a message or user | `!report @user reason` or `!report [message link] reason` | Everyone |
| `!setreportchannel` | Sets the channel where reports are sent | `!setreportchannel #channel` | Admin |

<!-- Innktober section removed as this feature is no longer available -->

## Summarization

Commands for text summarization.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!summarize` | Summarizes the provided text or linked content | `!summarize [text/URL]` | Everyone |
| `!summarizechannel` | Summarizes recent messages in a channel | `!summarizechannel [number of messages]` | Mod |

## Statistics

Commands for server statistics.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!stats` | Shows server statistics | `!stats` | Everyone |
| `!userstats` | Shows statistics for a specific user | `!userstats @user` | Everyone |
| `!channelstats` | Shows statistics for a specific channel | `!channelstats #channel` | Everyone |

## Owner Commands

Commands restricted to the bot owner.

| Command | Description | Usage | Permissions |
|---------|-------------|-------|------------|
| `!reload` | Reloads a cog | `!reload cog_name` | Owner |
| `!shutdown` | Shuts down the bot | `!shutdown` | Owner |
| `!eval` | Evaluates Python code | `!eval [code]` | Owner |
| `!load` | Loads a cog | `!load cog_name` | Owner |
| `!unload` | Unloads a cog | `!unload cog_name` | Owner |

## Slash Commands

The bot also supports Discord's slash commands for many of the features listed above. These commands start with `/` instead of `!` and provide an interactive interface with autocomplete options.

## Command Cooldowns

Some commands have cooldowns to prevent abuse. If you encounter a cooldown message, please wait before trying the command again.

## Permissions

- **Everyone**: All server members can use these commands
- **Mod**: Only moderators with appropriate permissions can use these commands
- **Admin**: Only administrators can use these commands
- **Owner**: Only the bot owner can use these commands

## Additional Features

### Automatic Reactions

The bot may automatically react to certain messages based on their content.

### Message Logging

The bot logs command usage and certain message events for statistical purposes.

### Error Handling

The bot includes comprehensive error handling to provide helpful error messages when commands fail.

### Database Integration

The bot stores data in a PostgreSQL database for persistence across restarts.

## Feature Requests

If you have ideas for new features, please contact the bot owner or submit a feature request through the appropriate channels.
