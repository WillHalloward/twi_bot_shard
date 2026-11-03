# Cognita Privacy Policy

_Last updated: 2026-11-03_

Cognita is a Discord bot run for The Wandering Inn community servers. This page
explains what data it collects, why, and how to have it removed.

## What we do not store

- **The text of your messages.** Cognita never saves message text to its
  database. It only records the number of characters in a message, which is
  used for activity statistics.
- **Message attachments, embeds or their URLs/filenames.**
- Message content is **never used to train machine-learning or AI models**.

## How message content is used

Cognita reads message content (via Discord's Message Content intent) only in
memory, for server moderation:

- **Edit/delete log**: when a message is edited or deleted, the before/after
  text is posted to a private moderator channel _inside Discord_.
- **Link detection**: messages containing links are forwarded to a private
  moderator channel _inside Discord_ for spam/phishing review.
- **Attachment logging**: attachments are re-posted to a private moderator
  channel _inside Discord_ so evidence survives if the original is deleted.

Nothing from these features is written to Cognita's database.

## What we store

To provide server statistics and moderation tools, Cognita stores:

- **Message metadata**: message ID, timestamp, server and channel, author ID,
  username and nickname, message length, reply reference, whether it was
  edited or deleted, and which users/roles it mentioned.
- **Attachment metadata**: attachment ID, file size, image dimensions and
  spoiler flag (no file, filename or link).
- **Reactions** (which emoji, by whom, on which message).
- **Membership events**: joins/leaves, role changes, thread membership and
  voice channel activity.
- **Command usage**: which bot commands were run, by whom, and when.

Data is stored in a PostgreSQL database hosted on Railway, encrypted at rest at
the storage layer and accessed only over encrypted connections. Only the bot's
maintainers have access. We do not sell or share this data with third parties.
Error reports sent to our error-tracking service (Sentry) are configured not to
include personal data.

## Retention and deletion

Metadata is kept for as long as the bot is running in the server, so long-term
statistics stay accurate. You can ask for all data about you to be deleted at
any time by messaging a moderator in The Wandering Inn Discord server or opening
an issue at <https://github.com/WillHalloward/twi_bot_shard/issues>. We will
remove it within 30 days.

## Changes

Changes to this policy are tracked in this repository's git history.
