# Cognita Bot Features

This document provides comprehensive documentation for all features and commands available in Cognita, the Discord bot for "The Wandering Inn" community.

## Table of Contents

- [Gallery & Mementos](#gallery--mementos)
- [Links & Tags](#links--tags)
- [Creator Links](#creator-links)
- [The Wandering Inn](#the-wandering-inn)
- [Patreon Polls](#patreon-polls)
- [Utility Commands](#utility-commands)
- [Self-Assignable Roles](#self-assignable-roles)
- [Quotes](#quotes)
- [Moderation](#moderation)
- [Reporting](#reporting)
- [Summarization](#summarization)
- [Statistics](#statistics)
- [Server Settings](#server-settings)
- [Help System](#help-system)
- [Owner Commands](#owner-commands)
- [Permissions Reference](#permissions-reference)

---

## Gallery & Mementos

The gallery system allows users to repost content from messages to designated gallery channels, supporting images, videos, links, and text.

### Repost (Context Menu)

Right-click on any message to repost its content to a designated gallery channel.

**Usage:** Right-click message > Apps > Repost

**Permissions:** Ban Members

**Supported Content Types:**
- Attachments (images, videos, audio, text files)
- AO3 links
- Twitter links
- Discord files
- Text content

**Process:**
1. Right-click on a message containing content you want to repost
2. Select "Apps" > "Repost" from the context menu
3. Select the type of content to repost (if multiple types are detected)
4. Select the destination channel from the dropdown menu
5. Optionally add a title and description
6. Submit to repost the content

### /gallery_admin set_repost

Adds or removes a channel from the list of channels where content can be reposted.

**Usage:** `/gallery_admin set_repost <channel>`

**Parameters:**
- `channel` (required): The channel to add or remove from the repost list

**Permissions:** Administrator

**Example:** `/gallery_admin set_repost #gallery`

---

## Links & Tags

Commands for managing server links organized by tags/categories.

### /link get

Retrieves and posts a link with the given name.

**Usage:** `/link get <title>`

**Parameters:**
- `title` (required): The title of the link to retrieve (supports autocomplete)

**Permissions:** Everyone

**Example:** `/link get discord`

### /link list

Lists all available links, optionally filtered by category.

**Usage:** `/link list [category]`

**Parameters:**
- `category` (optional): Filter links by a specific category

**Permissions:** Everyone

### /link add

Adds a new link with the given name, URL, and optional tag.

**Usage:** `/link add <content> <title> [tag] [embed]`

**Parameters:**
- `content` (required): The URL or content of the link
- `title` (required): The title/name for the link
- `tag` (optional): A tag to categorize the link
- `embed` (optional): Whether to display the link as an embed (default: True)

**Permissions:** Mod

**Example:** `/link add https://discord.gg/wanderinginn Discord server twi true`

### /link delete

Deletes a link with the given name.

**Usage:** `/link delete <title>`

**Parameters:**
- `title` (required): The title of the link to delete (supports autocomplete)

**Permissions:** Mod

**Example:** `/link delete discord`

### /link edit

Edits an existing link's content.

**Usage:** `/link edit <title> <content>`

**Parameters:**
- `title` (required): The title of the link to edit
- `content` (required): The new URL or content for the link

**Permissions:** Link owner or Admin (users can only edit links they added unless they have administrator permissions)

**Example:** `/link edit discord https://discord.gg/newlink`

### /tag

Shows all links with a specific tag.

**Usage:** `/tag <tag>`

**Parameters:**
- `tag` (required): The tag to search for

**Permissions:** Everyone

**Example:** `/tag twi`

---

## Creator Links

Allows users to manage and share their creator links (social media, portfolio, or other personal links).

### /creator_link get

Displays a user's creator links.

**Usage:** `/creator_link get [creator]`

**Parameters:**
- `creator` (optional): The user whose links you want to view. If not specified, shows your own links.

**Permissions:** Everyone

**Example:** `/creator_link get @username`

### /creator_link add

Adds a new link to your creator links.

**Usage:** `/creator_link add <title> <link> [nsfw] [weight] [feature]`

**Parameters:**
- `title` (required): The title/name for the link
- `link` (required): The URL
- `nsfw` (optional): Whether the link contains NSFW content (default: False)
- `weight` (optional): Priority weight for ordering links - higher values appear first (default: 0)
- `feature` (optional): Whether to feature this link (default: True)

**Permissions:** Everyone (own links only)

**Example:** `/creator_link add Twitter https://twitter.com/myusername false 10 true`

### /creator_link remove

Removes a link from your creator links.

**Usage:** `/creator_link remove <title>`

**Parameters:**
- `title` (required): The title of the link to remove

**Permissions:** Everyone (own links only)

**Example:** `/creator_link remove Twitter`

### /creator_link edit

Edits an existing link in your creator links.

**Usage:** `/creator_link edit <title> <link> [nsfw] [weight] [feature]`

**Parameters:**
- `title` (required): The title of the link to edit
- `link` (required): The new URL
- `nsfw` (optional): Whether the link contains NSFW content (default: False)
- `weight` (optional): Priority weight for ordering links (default: 0)
- `feature` (optional): Whether to feature this link (default: True)

**Permissions:** Everyone (own links only)

**Example:** `/creator_link edit Twitter https://twitter.com/mynewusername false 20 true`

---

## The Wandering Inn

Commands specific to The Wandering Inn web serial community.

### /password

Provides the current Patreon password for accessing locked chapters, or instructions on how to get it.

**Usage:** `/password`

**Permissions:** Everyone

**Behavior:**
- In allowed channels: Returns the current password and chapter link
- In other channels: Provides instructions on how to get the password via Discord, email, or Patreon

### /connectdiscord

Provides instructions on how to connect Patreon and Discord accounts.

**Usage:** `/connectdiscord`

**Permissions:** Everyone

### /wiki

Searches The Wandering Inn wiki for articles matching the query.

**Usage:** `/wiki <query>`

**Parameters:**
- `query` (required): The search term to look for (2-100 characters)

**Permissions:** Everyone

**Example:** `/wiki Erin Solstice`

### /find

Performs a Google search restricted to wanderinginn.com and returns the results.

**Usage:** `/find <query>`

**Parameters:**
- `query` (required): The search term to look for (2-200 characters)

**Permissions:** Everyone (bot channel only)

**Example:** `/find blue fruit tree`

### /invistext

Lists chapters containing invisible text, or displays the invisible text from a specific chapter.

**Usage:** `/invistext [chapter]`

**Parameters:**
- `chapter` (optional): The chapter name to get invisible text from (supports autocomplete). If not specified, lists all chapters with invisible text.

**Permissions:** Everyone

**Example:** `/invistext 1.08 R`

### /coloredtext

Displays a comprehensive list of all the different colored text used in The Wandering Inn, including hex codes and the chapters where they first appeared.

**Usage:** `/coloredtext`

**Permissions:** Everyone

### /update_password

Updates the Patreon password and chapter link in the database.

**Usage:** `/update_password <password> <link>`

**Parameters:**
- `password` (required): The new Patreon password (3-100 characters)
- `link` (required): The URL to the chapter that requires the password

**Permissions:** Admin (requires Ban Members permission and admin role)

**Example:** `/update_password secretpass123 https://wanderinginn.com/chapter`

---

## Patreon Polls

Commands for accessing and displaying information about Patreon polls.

### /poll

Displays the latest active poll or a specific poll by ID.

**Usage:** `/poll [poll_id]`

**Parameters:**
- `poll_id` (optional): The ID of a specific poll to display. If not specified, shows the latest active poll.

**Permissions:** Everyone

**Cooldown:** 60 seconds per user per channel

**Example:** `/poll 42`

### /polllist

Shows a list of polls for a specific year.

**Usage:** `/polllist [year]`

**Parameters:**
- `year` (optional): The year to list polls for. If not specified, shows polls for the current year.

**Permissions:** Everyone (bot channel only)

**Example:** `/polllist 2023`

### /getpoll

Fetches poll data from Patreon and updates the database.

**Usage:** `/getpoll`

**Permissions:** Mod (Ban Members permission)

### /findpoll

Searches poll questions for a given query.

**Usage:** `/findpoll <query>`

**Parameters:**
- `query` (required): The text to search for in poll questions

**Permissions:** Everyone

**Example:** `/findpoll Erin`

---

## Utility Commands

General utility commands for all users.

### /ping

Shows the bot's latency.

**Usage:** `/ping`

**Permissions:** Everyone

**Example Output:** `123 ms`

### /avatar

Displays a user's avatar in full size.

**Usage:** `/avatar [member]`

**Parameters:**
- `member` (optional): The user whose avatar you want to see. If not specified, shows your own avatar.

**Permissions:** Everyone

**Example:** `/avatar @username`

### /info user

Shows detailed information about a user.

**Usage:** `/info user [member]`

**Parameters:**
- `member` (optional): The user whose information you want to see. If not specified, shows your own information.

**Permissions:** Everyone

**Example:** `/info user @username`

### User info (Context Menu)

Shows detailed information about a user via context menu.

**Usage:** Right-click on a user > Apps > User info

**Permissions:** Everyone

### /info server

Shows detailed information about the server.

**Usage:** `/info server`

**Permissions:** Everyone

### /info role

Shows detailed information about a role.

**Usage:** `/info role <role>`

**Parameters:**
- `role` (required): The role to get information about

**Permissions:** Everyone

**Example:** `/info role @Moderator`

### /roll

Rolls dice with customizable parameters.

**Usage:** `/roll [dice] [amount] [modifier]`

**Parameters:**
- `dice` (optional): The type of dice to roll (default: 20)
- `amount` (optional): The number of dice to roll (default: 1)
- `modifier` (optional): A modifier to add to the result (default: 0)

**Permissions:** Everyone

**Example:** `/roll 20 2 5` (rolls 2d20+5)

### /ao3

Retrieves and displays detailed information about an AO3 work.

**Usage:** `/ao3 <ao3_url>`

**Parameters:**
- `ao3_url` (required): The URL of the AO3 work

**Permissions:** Everyone

**Example:** `/ao3 https://archiveofourown.org/works/12345678`

### /pat

Give Cognita a pat for a job well done.

**Usage:** `/pat`

**Permissions:** Everyone

### Pin (Context Menu)

Pins a message in channels where pinning is allowed.

**Usage:** Right-click on a message > Apps > Pin

**Permissions:** Everyone (only in designated pin channels)

### /admin set_pin_channels

Adds or removes a channel from the list of channels where messages can be pinned.

**Usage:** `/admin set_pin_channels <channel>`

**Parameters:**
- `channel` (required): The channel to add or remove from the pin-enabled list

**Permissions:** Administrator

**Example:** `/admin set_pin_channels #announcements`

---

## Self-Assignable Roles

Commands for managing and assigning roles to yourself.

### /roles

Lists all self-assignable roles in the server, organized by category.

**Usage:** `/roles`

**Permissions:** Everyone

### /role

Adds or removes a self-assignable role from yourself.

**Usage:** `/role <role>`

**Parameters:**
- `role` (required): The role to add or remove

**Permissions:** Everyone

**Example:** `/role @Artist`

### /admin_role add

Adds a role to the self-assignable roles list.

**Usage:** `/admin_role add <role> [category] [auto_replace] [required_roles]`

**Parameters:**
- `role` (required): The role to make self-assignable
- `category` (optional): The category for grouping roles (default: "Uncategorized")
- `auto_replace` (optional): Whether to automatically replace other roles in the same category (default: False)
- `required_roles` (optional): Space-separated list of role mentions required to get this role

**Permissions:** Administrator

**Example:** `/admin_role add @Artist Art true @Member`

### /admin_role remove

Removes a role from the self-assignable roles list.

**Usage:** `/admin_role remove <role>`

**Parameters:**
- `role` (required): The role to remove from self-assignable roles

**Permissions:** Administrator

**Example:** `/admin_role remove @Artist`

### /admin_role weight

Changes the weight of a role for ordering in the roles list.

**Usage:** `/admin_role weight <role> <new_weight>`

**Parameters:**
- `role` (required): The role to update
- `new_weight` (required): The new weight value (lower values appear first)

**Permissions:** Administrator

**Example:** `/admin_role weight @Artist 10`

---

## Quotes

Commands for managing server quotes.

### /quote add

Adds a quote to the database.

**Usage:** `/quote add <quote>`

**Parameters:**
- `quote` (required): The quote text to add

**Permissions:** Everyone

**Example:** `/quote add This is a memorable quote`

### /quote get

Gets a random quote or a specific quote by index.

**Usage:** `/quote get [index]`

**Parameters:**
- `index` (optional): The index of the quote to get (supports autocomplete). If not specified, returns a random quote.

**Permissions:** Everyone

**Example:** `/quote get 42`

### /quote find

Searches for quotes containing specific text.

**Usage:** `/quote find <search>`

**Parameters:**
- `search` (required): The text to search for in quotes

**Permissions:** Everyone

**Example:** `/quote find memorable`

### /quote who

Shows who added a specific quote.

**Usage:** `/quote who <index>`

**Parameters:**
- `index` (required): The index of the quote (supports autocomplete)

**Permissions:** Everyone

**Example:** `/quote who 42`

### /quote delete

Deletes a quote by its index.

**Usage:** `/quote delete <delete>`

**Parameters:**
- `delete` (required): The index of the quote to delete (supports autocomplete)

**Permissions:** Everyone

**Example:** `/quote delete 42`

---

## Moderation

Commands for server moderation.

### /mod reset

Resets the cooldown of a command.

**Usage:** `/mod reset <command>`

**Parameters:**
- `command` (required): The name of the command to reset the cooldown for

**Permissions:** Mod (Ban Members permission)

**Example:** `/mod reset link_add`

### /mod state

Makes Cognita post an official moderator message with special formatting.

**Usage:** `/mod state <message>`

**Parameters:**
- `message` (required): The message content to be posted

**Permissions:** Mod (Ban Members permission)

**Example:** `/mod state Please remember to follow the server rules.`

### Automatic Features

The moderation system includes several automatic features:

- **Attachment Logging**: Logs all attachments posted in the server to a webhook for moderation purposes
- **DM Logging**: Logs all direct messages sent to the bot, including text and attachments
- **Link Detection**: Monitors messages for links in specific servers and logs them for moderation review
- **New User Filtering**: Automatically assigns a verified role to users with Discord accounts older than 72 hours

---

## Reporting

The reporting system allows users to report problematic messages to moderators.

### Report (Context Menu)

Right-click on any message to report it to moderators.

**Usage:** Right-click message > Apps > Report

**Permissions:** Everyone

**Report Reasons:**
- Spam
- NSFW
- Harassment
- Other
- Wrong Channel
- Spoiler

**Process:**
1. Right-click on a message you want to report
2. Select "Apps" > "Report" from the context menu
3. Select a reason for the report from the dropdown menu
4. Choose whether to report anonymously or not
5. Optionally add additional information
6. Submit the report

---

## Summarization

AI-powered conversation summarization and moderation using OpenAI.

### /summarize

Summarizes the last X messages in the channel using AI.

**Usage:** `/summarize [num_messages]`

**Parameters:**
- `num_messages` (optional): The number of messages to summarize (default: 50)

**Permissions:** Everyone

**Example:** `/summarize 100`

### /moderate

Analyzes the last X messages for potential rule violations.

**Usage:** `/moderate [num_messages]`

**Parameters:**
- `num_messages` (optional): The number of messages to check for rule violations (default: 50)

**Permissions:** Mod (response is ephemeral - only visible to the user who ran it)

**Example:** `/moderate 100`

---

## Statistics

Statistics are automatically tracked by the bot. The stats system monitors server activity including messages, members, channels, roles, and more.

### /messagecount

Retrieves the count of messages in a specified channel over a specified number of hours.

**Usage:** `/messagecount <channel> <hours>`

**Parameters:**
- `channel` (required): The channel to count messages in
- `hours` (required): The number of hours to look back

**Permissions:** Everyone

**Example:** `/messagecount #general 24`

### Automatic Tracking

The statistics system automatically tracks:

**Message Events:**
- New messages
- Message edits (with before/after content)
- Message deletions
- Reactions added and removed

**Member Events:**
- Member joins and leaves
- Role changes
- Username changes

**Channel Events:**
- Channel creation and deletion
- Channel updates (name, category, position, topic, NSFW status)
- Thread creation, deletion, and updates
- Thread membership

**Server Events:**
- Server name changes
- Emoji additions and removals
- Role creation, deletion, and updates
- Voice channel activity (joins, leaves, moves, mute/deaf status)

### Daily Stats Report

An automated report is generated every 24 hours showing:
- Message counts by channel (organized by category with thread nesting)
- Member join/leave statistics

---

## Server Settings

Commands for managing server-specific configuration.

### /set_admin_role

Sets the admin role for the server. Users with this role will have elevated permissions for certain bot commands.

**Usage:** `/set_admin_role <role>`

**Parameters:**
- `role` (required): The role to set as the admin role

**Permissions:** Manage Messages

**Example:** `/set_admin_role @Moderator`

### /get_admin_role

Displays the currently configured admin role for the server.

**Usage:** `/get_admin_role`

**Permissions:** Everyone

---

## Help System

Interactive help system for navigating bot commands.

### /help

Displays an interactive help system with command categories.

**Usage:** `/help [command]`

**Parameters:**
- `command` (optional): The name of a specific command to get detailed help for. If not specified, shows the interactive help menu.

**Permissions:** Everyone

**Example:** `/help summarize`

**Features:**
- **Category Selection**: A dropdown menu to browse commands by category
- **Command Details**: Detailed information including syntax, examples, and required permissions
- **Navigation**: Back button to return to category view
- **Timeout**: The interactive view times out after 60 seconds of inactivity

**Command Categories:**
| Category | Description |
|----------|-------------|
| Moderation | Commands for moderating your server |
| Utility | General utility commands |
| Configuration | Server configuration commands |
| Gallery | Image gallery management commands |
| Creator Links | Creator link management commands |
| Statistics | Statistics tracking commands |
| Other | Miscellaneous commands |

---

## Owner Commands

Commands restricted to the bot owner for bot management.

### /admin load

Loads a cog into the bot.

**Usage:** `/admin load <cog>`

**Parameters:**
- `cog` (required): The name of the cog to load (supports autocomplete)

**Permissions:** Owner

**Example:** `/admin load cogs.gallery`

### /admin unload

Unloads a cog from the bot.

**Usage:** `/admin unload <cog>`

**Parameters:**
- `cog` (required): The name of the cog to unload (supports autocomplete)

**Permissions:** Owner

**Example:** `/admin unload cogs.gallery`

### /admin reload

Reloads a cog (unloads and then loads it).

**Usage:** `/admin reload <cog>`

**Parameters:**
- `cog` (required): The name of the cog to reload (supports autocomplete)

**Permissions:** Owner

**Example:** `/admin reload cogs.gallery`

### /admin loadall

Loads all unloaded cogs at once.

**Usage:** `/admin loadall`

**Permissions:** Owner

### /admin sync

Syncs the bot's command tree either globally or locally.

**Usage:** `/admin sync <all_guilds>`

**Parameters:**
- `all_guilds` (required): Whether to sync globally (True) or just for the current guild (False)

**Permissions:** Owner

**Example:** `/admin sync True`

### /admin cmd

Executes a shell command on the host system.

**Usage:** `/admin cmd <args>`

**Parameters:**
- `args` (required): The command and arguments to execute

**Permissions:** Owner

**Example:** `/admin cmd ls -la`

### /admin exit

Shuts down the bot.

**Usage:** `/admin exit`

**Permissions:** Owner

### /admin resources

Displays bot resource usage statistics including memory, CPU, database cache, and HTTP client statistics.

**Usage:** `/admin resources [detail_level]`

**Parameters:**
- `detail_level` (optional): The level of detail to display. Options: "basic" (default), "detailed", "system"

**Permissions:** Owner

**Example:** `/admin resources detailed`

### /admin sql

Executes a SQL query on the database with security restrictions.

**Usage:** `/admin sql <query> [allow_modifications]`

**Parameters:**
- `query` (required): The SQL query to execute
- `allow_modifications` (optional): Whether to allow INSERT, UPDATE, DELETE operations (default: False)

**Permissions:** Owner

**Example:** `/admin sql SELECT COUNT(*) FROM messages WHERE server_id = 12345`

### /admin ask_db

Ask a natural language question about the database and get SQL results. Uses AI to convert questions into SQL queries.

**Usage:** `/admin ask_db <question>`

**Parameters:**
- `question` (required): The natural language question to ask about the database

**Permissions:** Owner

**Example:** `/admin ask_db How many messages were sent in general yesterday?`

### /say

Makes the bot say something.

**Usage:** `/say <say> [channel]`

**Parameters:**
- `say` (required): The message for the bot to say
- `channel` (optional): The channel to send the message to (defaults to current channel)

**Permissions:** Owner

**Example:** `/say Hello everyone!`

---

## Permissions Reference

| Permission Level | Description |
|------------------|-------------|
| **Everyone** | All server members can use these commands |
| **Mod** | Users with Ban Members permission can use these commands |
| **Admin** | Users with Administrator permission or the configured admin role |
| **Owner** | Only the bot owner can use these commands |

### Command Cooldowns

Some commands have cooldowns to prevent abuse. If you encounter a cooldown message, please wait before trying the command again.

---

## Feature Requests

If you have ideas for new features, please contact the bot owner or submit a feature request through the appropriate channels.
