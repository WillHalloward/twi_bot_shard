# Archived Code Snippets

This document contains code snippets that have been removed from the codebase but might be useful for reference in the future. Each snippet includes information about where it was removed from, when it was removed, and why.

## Reddit Verification (from cogs/twi.py)

**Removed on**: [Current Date]

**Reason for removal**: This functionality was commented out and unused. It appears to be related to Reddit verification for Patreon subscribers, but the feature is no longer active or needed.

**Original location**: cogs/twi.py

```python
@commands.command(name="reddit")
async def reddit_verification(self, interaction, username):
    if username.startswith("/"):
        logging.info("Removing first /")
        username = username[1:]
    if username.startswith("u/"):
        logging.info("Removing u/")
        username = username[2:]
    logging.info(f"Trying to find user {username}")
    try:
        reddit.subreddit("TWI_Patreon").contributor.add(username)
    except RedditAPIException as exception:
        for subexception in exception.items:
            logging.error(subexception)
    try:
        await self.bot.db.execute(
            """INSERT INTO twi_reddit(
            time_added, discord_username, discord_id, reddit_username, currant_patreon, subreddit
            )
            VALUES (NOW(), $1, $2, $3, True, 'TWI_patreon')""",
            interaction.author.name, interaction.author.id, username
        )
    except asyncpg.UniqueViolationError as e:
        logging.exception(f'{e}')
        dup_user = await self.bot.db.fetchrow("SELECT reddit_username FROM twi_reddit WHERE discord_id = $1",
                                               interaction.author.id)
        await interaction.response.send_message(f"You are already in the list with username {dup_user['reddit_username']}")
```

**Notes**: This code was designed to add Discord users to a private TWI_Patreon subreddit. It would:
1. Clean up the provided Reddit username (removing "/" or "u/" prefixes)
2. Add the user as a contributor to the TWI_Patreon subreddit
3. Record the association between Discord and Reddit usernames in the database
4. Handle the case where a user was already in the database

If this functionality needs to be restored in the future, note that it would need to be updated to work with Discord's newer interaction-based commands rather than the older command context system.

## Bot Channel Check (from cogs/patreon_poll.py)

**Removed on**: [Current Date]

**Reason for removal**: This decorator was commented out and no longer needed. The poll command has a cooldown check instead of a channel restriction, allowing it to be used in any channel but with rate limiting to prevent spam.

**Original location**: cogs/patreon_poll.py, line 148

```python
# @commands.check(is_bot_channel)
```

**Notes**: This was a channel restriction that would have limited the poll command to designated bot channels. It was replaced with a cooldown check that allows the command to be used in any channel but limits how frequently it can be used.
