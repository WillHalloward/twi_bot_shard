# Cognita Bot Cogs Documentation

This document provides comprehensive documentation for all cogs in the Cognita Discord bot, including command usage examples and configuration options.

## Table of Contents

- [Introduction](#introduction)
- [Cog Documentation](#cog-documentation)
  - [Creator Links](#creator-links)
  - [Gallery](#gallery)
  <!-- Innktober section removed -->
  - [Links Tags](#links-tags)
  - [Mods](#mods)
  - [Other](#other)
  - [Owner](#owner)
  - [Patreon Poll](#patreon-poll)
  - [Report](#report)
  - [Stats](#stats)
  - [Summarization](#summarization)
  - [TWI](#twi)

## Introduction

Cognita is a Discord bot designed for "The Wandering Inn" server. Each cog represents a modular component of the bot that provides specific functionality. This documentation explains how to use each cog's commands and configure its options.

## Cog Documentation

### Creator Links

The Creator Links cog allows users to manage and share their creator links (such as social media, portfolio, or other personal links).

#### Commands

##### /creator_link get
**Description:** Displays a user's creator links.
**Usage:** `/creator_link get [creator]`
**Parameters:**
- `creator` (optional): The user whose links you want to view. If not specified, shows your own links.
**Example:** `/creator_link get @username`

##### /creator_link add
**Description:** Adds a new link to your creator links.
**Usage:** `/creator_link add <title> <link> [nsfw] [weight] [feature]`
**Parameters:**
- `title` (required): The title/name for the link
- `link` (required): The URL
- `nsfw` (optional): Whether the link contains NSFW content (default: False)
- `weight` (optional): Priority weight for ordering links (default: 0)
- `feature` (optional): Whether to feature this link (default: True)
**Example:** `/creator_link add Twitter https://twitter.com/myusername false 10 true`

##### /creator_link remove
**Description:** Removes a link from your creator links.
**Usage:** `/creator_link remove <title>`
**Parameters:**
- `title` (required): The title of the link to remove
**Example:** `/creator_link remove Twitter`

##### /creator_link edit
**Description:** Edits an existing link in your creator links.
**Usage:** `/creator_link edit <title> <link> [nsfw] [weight] [feature]`
**Parameters:**
- `title` (required): The title of the link to edit
- `link` (required): The new URL
- `nsfw` (optional): Whether the link contains NSFW content (default: False)
- `weight` (optional): Priority weight for ordering links (default: 0)
- `feature` (optional): Whether to feature this link (default: True)
**Example:** `/creator_link edit Twitter https://twitter.com/mynewusername false 20 true`

#### Database
This cog uses the `creator_links` table in the database with the following structure:
- `user_id`: The Discord user ID
- `title`: The title/name of the link
- `link`: The URL
- `nsfw`: Boolean indicating if the link contains NSFW content
- `weight`: Integer for ordering links (higher values appear first)
- `feature`: Boolean indicating if the link should be featured
- `last_changed`: Timestamp of when the link was last modified

### Gallery

The Gallery & Mementos cog provides functionality for reposting content from messages to designated channels, including images, videos, links, and text.

#### Commands

##### Repost (Context Menu)
**Description:** Context menu command that allows reposting content from a message to a designated gallery channel.
**Usage:** Right-click on a message > Apps > Repost
**Permissions Required:** Ban Members permission
**Supported Content Types:**
- Attachments (images, videos, audio, text files)
- AO3 links
- Twitter links
- Instagram links (not currently supported)
- Discord files
- Text content

**Process:**
1. Right-click on a message containing content you want to repost
2. Select "Apps" > "Repost" from the context menu
3. Select the type of content to repost (if multiple types are detected)
4. Select the destination channel from the dropdown menu
5. Optionally add a title and description
6. Submit to repost the content

##### /set_repost
**Description:** Adds or removes a channel from the list of channels where content can be reposted.
**Usage:** `/set_repost <channel>`
**Parameters:**
- `channel` (required): The channel to add or remove from the repost list
**Permissions Required:** Administrator
**Example:** `/set_repost #gallery`

#### Dependencies
This cog requires several external libraries:
- gallery_dl: For downloading content from Twitter
- ao3: For fetching AO3 work information
- aiohttp: For downloading files

#### Database
This cog uses the `gallery_mementos` table in the database to store channels where content can be reposted:
- `channel_name`: The name of the channel
- `channel_id`: The Discord channel ID
- `guild_id`: The Discord guild (server) ID

<!-- Innktober section removed as this feature is no longer available -->

### Links Tags

The Links Tags cog provides functionality for managing and retrieving links with associated tags.

#### Commands

##### /link get
**Description:** Gets a link with the given name.
**Usage:** `/link get <title>`
**Parameters:**
- `title` (required): The title of the link to retrieve (supports autocomplete)
**Example:** `/link get discord`

##### /link list
**Description:** Lists all available links.
**Usage:** `/link list`

##### /link add
**Description:** Adds a new link with the given name, URL, and optional tag.
**Usage:** `/link add <content> <title> [tag] [embed]`
**Parameters:**
- `content` (required): The URL or content of the link
- `title` (required): The title/name for the link
- `tag` (optional): A tag to categorize the link
- `embed` (optional): Whether to display the link as an embed (default: True)
**Example:** `/link add https://discord.gg/wanderinginn Discord server twi true`

##### /link delete
**Description:** Deletes a link with the given name.
**Usage:** `/link delete <title>`
**Parameters:**
- `title` (required): The title of the link to delete (supports autocomplete)
**Example:** `/link delete discord`

##### /link edit
**Description:** Edits an existing link with the given name.
**Usage:** `/link edit <title> <content>`
**Parameters:**
- `title` (required): The title of the link to edit
- `content` (required): The new URL or content for the link
**Permissions:** Users can only edit links they added themselves, unless they have administrator permissions
**Example:** `/link edit discord https://discord.gg/newlink`

##### /tags
**Description:** Shows all available tags.
**Usage:** `/tags`

##### /tag
**Description:** Shows all links with a specific tag.
**Usage:** `/tag <tag>`
**Parameters:**
- `tag` (required): The tag to search for
**Example:** `/tag twi`

#### Database
This cog uses the `links` table in the database with the following structure:
- `title`: The title/name of the link
- `content`: The URL or content of the link
- `tag`: Optional tag for categorization
- `user_who_added`: Display name of the user who added the link
- `id_user_who_added`: Discord ID of the user who added the link
- `time_added`: Timestamp of when the link was added
- `embed`: Boolean indicating if the link should be displayed as an embed
- `guild_id`: The Discord guild (server) ID

### Mods

The Mods cog provides moderation tools and logging functionality for server administrators.

#### Commands

##### /reset
**Description:** Resets the cooldown of a command.
**Usage:** `/reset <command>`
**Parameters:**
- `command` (required): The name of the command to reset the cooldown for
**Permissions Required:** Ban Members permission
**Example:** `/reset link_add`

##### /state
**Description:** Makes Cognita post a mod message with special formatting.
**Usage:** `/state <message>`
**Parameters:**
- `message` (required): The message content to be posted
**Permissions Required:** Ban Members permission
**Example:** `/state Please remember to follow the server rules.`

#### Event Listeners

The cog also includes several automatic event listeners that don't require commands:

##### Attachment Logging
Automatically logs all attachments posted in the server to a webhook for moderation purposes.

##### DM Logging
Logs all direct messages sent to the bot to a webhook, including both text and attachments.

##### Link Detection
Monitors messages for links in a specific server and logs them to a webhook for moderation review.

##### New User Filtering
Automatically adds a verified role to users who have Discord accounts older than 72 hours when they join the server.

#### Configuration
This cog requires webhook URLs to be configured in the `.env` file:
- `WEBHOOK`: For logging attachments and links
- `WEBHOOK_TESTING_LOG`: For logging direct messages

#### Dependencies
- aiohttp: For sending webhook requests

### Other

The Other cog provides a variety of utility commands for general server use.

#### Commands

##### /ping
**Description:** Shows the bot's latency.
**Usage:** `/ping`
**Example Output:** `123 ms`

##### /avatar
**Description:** Displays a user's avatar in full size.
**Usage:** `/avatar [member]`
**Parameters:**
- `member` (optional): The user whose avatar you want to see. If not specified, shows your own avatar.
**Example:** `/avatar @username`

##### /info user
**Description:** Shows detailed information about a user.
**Usage:** `/info user [member]`
**Parameters:**
- `member` (optional): The user whose information you want to see. If not specified, shows your own information.
**Example:** `/info user @username`

##### User info (Context Menu)
**Description:** Shows detailed information about a user via context menu.
**Usage:** Right-click on a user > Apps > User info

##### /info server
**Description:** Shows detailed information about the server.
**Usage:** `/info server`

##### /info role
**Description:** Shows detailed information about a role.
**Usage:** `/info role <role>`
**Parameters:**
- `role` (required): The role to get information about
**Example:** `/info role @Moderator`

##### /say
**Description:** Makes the bot say something.
**Usage:** `/say <say>`
**Parameters:**
- `say` (required): The message for the bot to say
**Permissions Required:** Bot Owner
**Example:** `/say Hello everyone!`

##### /saychannel
**Description:** Makes the bot say something in a specific channel.
**Usage:** `/saychannel <channel> <say>`
**Parameters:**
- `channel` (required): The channel to send the message to
- `say` (required): The message for the bot to say
**Permissions Required:** Bot Owner
**Example:** `/saychannel #general Hello everyone!`

##### /quote add
**Description:** Adds a quote to the database.
**Usage:** `/quote add <quote>`
**Parameters:**
- `quote` (required): The quote text to add
**Example:** `/quote add This is a memorable quote`

##### /quote find
**Description:** Searches for quotes containing specific text.
**Usage:** `/quote find <search>`
**Parameters:**
- `search` (required): The text to search for in quotes
**Example:** `/quote find memorable`

##### /quote delete
**Description:** Deletes a quote by its index.
**Usage:** `/quote delete <delete>`
**Parameters:**
- `delete` (required): The index of the quote to delete (supports autocomplete)
**Example:** `/quote delete 42`

##### /quote get
**Description:** Gets a random quote or a specific quote by index.
**Usage:** `/quote get [index]`
**Parameters:**
- `index` (optional): The index of the quote to get (supports autocomplete). If not specified, returns a random quote.
**Example:** `/quote get 42`

##### /quote who
**Description:** Shows who added a specific quote.
**Usage:** `/quote who <index>`
**Parameters:**
- `index` (required): The index of the quote (supports autocomplete)
**Example:** `/quote who 42`

##### /roles
**Description:** Lists all self-assignable roles in the server, organized by category.
**Usage:** `/roles`

##### /admin_role weight
**Description:** Changes the weight of a role for ordering in the roles list.
**Usage:** `/admin_role weight <role> <new_weight>`
**Parameters:**
- `role` (required): The role to update
- `new_weight` (required): The new weight value (lower values appear first)
**Permissions Required:** Administrator
**Example:** `/admin_role weight @Artist 10`

##### /admin_role add
**Description:** Adds a role to the self-assignable roles list.
**Usage:** `/admin_role add <role> [category] [auto_replace] [required_roles]`
**Parameters:**
- `role` (required): The role to make self-assignable
- `category` (optional): The category for grouping roles (default: "Uncategorized")
- `auto_replace` (optional): Whether to automatically replace other roles in the same category (default: False)
- `required_roles` (optional): Space-separated list of role mentions required to get this role
**Permissions Required:** Administrator
**Example:** `/admin_role add @Artist Art true @Member`

##### /admin_role remove
**Description:** Removes a role from the self-assignable roles list.
**Usage:** `/admin_role remove <role>`
**Parameters:**
- `role` (required): The role to remove from self-assignable roles
**Permissions Required:** Administrator
**Example:** `/admin_role remove @Artist`

##### /role
**Description:** Adds or removes a self-assignable role from yourself.
**Usage:** `/role <role>`
**Parameters:**
- `role` (required): The role to add or remove
**Example:** `/role @Artist`

##### /roll
**Description:** Rolls dice with customizable parameters.
**Usage:** `/roll [dice] [amount] [modifier]`
**Parameters:**
- `dice` (optional): The type of dice to roll (default: 20)
- `amount` (optional): The number of dice to roll (default: 1)
- `modifier` (optional): A modifier to add to the result (default: 0)
**Example:** `/roll 20 2 5` (rolls 2d20+5)

##### /gallery_stats
**Description:** Generates an Excel spreadsheet with statistics about the gallery channel.
**Usage:** `/gallery_stats`

##### /ao3
**Description:** Retrieves and displays detailed information about an AO3 work.
**Usage:** `/ao3 <ao3_url>`
**Parameters:**
- `ao3_url` (required): The URL of the AO3 work
**Example:** `/ao3 https://archiveofourown.org/works/12345678`

##### Pin (Context Menu)
**Description:** Pins a message in channels where pinning is allowed.
**Usage:** Right-click on a message > Apps > Pin

##### /set_pin_channels
**Description:** Adds or removes a channel from the list of channels where messages can be pinned.
**Usage:** `/set_pin_channels <channel>`
**Parameters:**
- `channel` (required): The channel to add or remove from the pin-enabled list
**Permissions Required:** Administrator
**Example:** `/set_pin_channels #announcements`

#### Event Listeners

##### Role Update Notifications
Sends special messages when users get certain roles themed around "The Wandering Inn".

#### Database
This cog uses several database tables:
- `quotes`: Stores quotes added by users
- `roles`: Stores information about self-assignable roles
- `channels`: Stores information about channels where pinning is allowed

#### Dependencies
- openpyxl: For generating Excel spreadsheets
- AO3: For retrieving information about AO3 works

### Owner

The Owner cog provides commands for bot management that are restricted to the bot owner.

#### Commands

##### /load
**Description:** Loads a cog into the bot.
**Usage:** `/load <cog>`
**Parameters:**
- `cog` (required): The name of the cog to load (supports autocomplete)
**Permissions Required:** Bot Owner
**Guild Restriction:** Only works in guild ID 297916314239107072
**Example:** `/load cogs.gallery`

##### /unload
**Description:** Unloads a cog from the bot.
**Usage:** `/unload <cog>`
**Parameters:**
- `cog` (required): The name of the cog to unload (supports autocomplete)
**Permissions Required:** Bot Owner
**Guild Restriction:** Only works in guild ID 297916314239107072
**Example:** `/unload cogs.gallery`

##### /reload
**Description:** Reloads a cog (unloads and then loads it).
**Usage:** `/reload <cog>`
**Parameters:**
- `cog` (required): The name of the cog to reload (supports autocomplete)
**Permissions Required:** Bot Owner
**Guild Restriction:** Only works in guild ID 297916314239107072
**Example:** `/reload cogs.gallery`

##### /cmd
**Description:** Executes a shell command on the host system.
**Usage:** `/cmd <args>`
**Parameters:**
- `args` (required): The command and arguments to execute
**Permissions Required:** Bot Owner
**Guild Restriction:** Only works in guild ID 297916314239107072
**Example:** `/cmd ls -la`

##### /sync
**Description:** Syncs the command tree either globally or locally.
**Usage:** `/sync <all_guilds>`
**Parameters:**
- `all_guilds` (required): Whether to sync globally (True) or just for the current guild (False)
**Permissions Required:** Bot Owner
**Guild Restriction:** Only works in guild ID 297916314239107072
**Example:** `/sync True`

##### /exit
**Description:** Shuts down the bot.
**Usage:** `/exit`
**Permissions Required:** Bot Owner
**Guild Restriction:** Only works in guild ID 297916314239107072

#### Configuration
This cog has a predefined list of cogs that can be loaded, unloaded, or reloaded:
```python
cogs = ['cogs.summarization','cogs.gallery', 'cogs.links_tags', 'cogs.patreon_poll', 'cogs.twi', 'cogs.owner', 'cogs.other', 'cogs.mods', 'cogs.stats', 'cogs.creator_links', 'cogs.report', 'cogs.settings']
```

### Patreon Poll

The Patreon Poll cog provides commands for accessing and displaying information about Patreon polls for "The Wandering Inn".

#### Commands

##### /poll
**Description:** Displays the latest active poll or a specific poll by ID.
**Usage:** `/poll [poll_id]`
**Parameters:**
- `poll_id` (optional): The ID of a specific poll to display. If not specified, shows the latest active poll.
**Cooldown:** 60 seconds per user per channel
**Example:** `/poll 42`

##### /polllist
**Description:** Shows a list of polls for a specific year.
**Usage:** `/polllist [year]`
**Parameters:**
- `year` (optional): The year to list polls for. If not specified, shows polls for the current year.
**Channel Restriction:** Only works in channel ID 361694671631548417
**Example:** `/polllist 2023`

##### /getpoll
**Description:** Fetches poll data from Patreon and updates the database.
**Usage:** `/getpoll`
**Permissions Required:** Ban Members permission
**Example:** `/getpoll`

##### /findpoll
**Description:** Searches poll questions for a given query.
**Usage:** `/findpoll <query>`
**Parameters:**
- `query` (required): The text to search for in poll questions
**Example:** `/findpoll Erin`

#### Database
This cog uses the following database tables:
- `poll`: Stores poll metadata
  - `id`: Poll ID
  - `title`: Poll title
  - `start_date`: When the poll started
  - `expire_date`: When the poll expires/expired
  - `poll_url`: URL to the poll on Patreon
  - `api_url`: URL to the poll's API endpoint
  - `expired`: Boolean indicating if the poll has expired
  - `index_serial`: Sequential index for the poll
- `poll_option`: Stores poll options
  - `poll_id`: ID of the poll this option belongs to
  - `option_text`: Text of the option
  - `num_votes`: Number of votes for this option
  - `tokens`: Text search vector for searching

#### Configuration
This cog requires Patreon cookies to be configured in the `.env` file as a JSON string for fetching poll data directly from Patreon's API.

#### Dependencies
- aiohttp: For making HTTP requests to Patreon's API
- json: For parsing API responses

### Report

The Report cog provides functionality for users to report problematic messages to moderators.

#### Commands

##### Report (Context Menu)
**Description:** Context menu command that allows users to report a message.
**Usage:** Right-click on a message > Apps > Report
**Process:**
1. Right-click on a message you want to report
2. Select "Apps" > "Report" from the context menu
3. Select a reason for the report from the dropdown menu (Spam, NSFW, Harassment, Other, Wrong Channel, Spoiler)
4. Choose whether to report anonymously or not
5. Optionally add additional information
6. Submit the report

#### Database
This cog uses the `reports` table in the database to store report information:
- `message_id`: The ID of the reported message
- `user_id`: The ID of the user who submitted the report
- `reason`: The reason for the report
- `anonymous`: Whether the report was submitted anonymously
- `additional_info`: Additional information provided by the reporter

#### Note
This cog appears to be partially implemented, with some functionality still in development.

### Stats

The Stats cog provides comprehensive tracking and reporting of server activity statistics.

#### Commands

##### /messagecount
**Description:** Retrieves the count of messages in a specified channel over a specified number of hours.
**Usage:** `/messagecount <channel> <hours>`
**Parameters:**
- `channel` (required): The channel to count messages in
- `hours` (required): The number of hours to look back
**Example:** `/messagecount #general 24`

#### Automated Tasks

##### Daily Stats Report
The cog includes an automated task that runs every 24 hours to generate and post a report of server activity:
- Message counts by channel
- Member join/leave statistics

The report is posted to a specific channel (ID: 871486325692432464).

#### Event Listeners

The cog includes numerous event listeners that track changes to various Discord entities:

##### Message Events
- Message creation, editing, and deletion
- Reaction addition and removal

##### Member Events
- Member joins and leaves
- Role updates
- User profile updates

##### Channel Events
- Channel creation, deletion, and updates
- Thread creation, deletion, and updates
- Thread member joins and leaves

##### Server Events
- Server updates
- Emoji updates
- Role creation, deletion, and updates
- Voice state updates

#### Database
This cog uses several database tables and materialized views:
- `messages`: Stores message data
- `reactions`: Stores reaction data
- `users`: Stores user data
- `servers`: Stores server data
- `channels`: Stores channel data
- `emotes`: Stores emoji data
- `categories`: Stores category data
- `threads`: Stores thread data
- `roles`: Stores role data
- `updates`: Tracks changes to various Discord entities
- `daily_message_stats`: A materialized view for message statistics
- `daily_member_stats`: A materialized view for member join/leave statistics

#### Dependencies
- asyncpg: For database operations
- discord.ext.tasks: For scheduling the daily stats report

### Summarization

The Summarization cog provides AI-powered conversation summarization and moderation using OpenAI's GPT models.

#### Commands

##### /summarize
**Description:** Summarizes the last X messages in the channel.
**Usage:** `/summarize [num_messages]`
**Parameters:**
- `num_messages` (optional): The number of messages to summarize (default: 50)
**Example:** `/summarize 100`

##### /moderate
**Description:** Summarizes the last X messages and checks for rule violations.
**Usage:** `/moderate [num_messages]`
**Parameters:**
- `num_messages` (optional): The number of messages to check for rule violations (default: 50)
**Note:** This command's response is ephemeral (only visible to the user who ran it)
**Example:** `/moderate 100`

#### Configuration
The cog is configured with a list of server rules that are used for moderation:
```python
server_rules = [
    "Follow the Discord Community Guidelines.",
    "Don't spam or ping excessively, including images, emotes, or gifs.",
    "Don't attack other users.",
    "Don't post personal information.",
    "No bug pictures."
]
```

#### Dependencies
- openai: For accessing OpenAI's API

#### API Keys
This cog requires an OpenAI API key to be configured in the `.env` file:
```
OPENAI_API_KEY=your_api_key_here
```

<!-- Each cog will be documented in this section -->
