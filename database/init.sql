-- Database Initialization Script for Twi Bot Shard
-- This script creates all required tables, sequences, and indexes from scratch.
-- Run this on a fresh Railway PostgreSQL database.

-- ============================================================================
-- PART 1: CREATE SEQUENCES
-- ============================================================================
-- These sequences are referenced by tables and must exist first

CREATE SEQUENCE IF NOT EXISTS "foliana-interlude_serial_id_seq";
CREATE SEQUENCE IF NOT EXISTS invisible_text_twi_serial_id_seq;
CREATE SEQUENCE IF NOT EXISTS patreon_twi_serial_id_seq;
CREATE SEQUENCE IF NOT EXISTS poll_index_serial_seq;
CREATE SEQUENCE IF NOT EXISTS protected_is_public_serial_id_seq;
CREATE SEQUENCE IF NOT EXISTS tags_id_seq;  -- Used by links table
CREATE SEQUENCE IF NOT EXISTS wandering_inn_serial_id_seq;
CREATE SEQUENCE IF NOT EXISTS webhook_pins_twi_serial_id_seq;
CREATE SEQUENCE IF NOT EXISTS infractions_id_seq;

-- ============================================================================
-- PART 2: CREATE BASE TABLES (no foreign key dependencies)
-- ============================================================================

-- Users table (referenced by many other tables)
CREATE TABLE IF NOT EXISTS users
(
    serial_id  serial,
    user_id    bigint NOT NULL
        CONSTRAINT users_pk PRIMARY KEY,
    created_at timestamp DEFAULT '1970-01-01 00:00:00'::timestamp without time zone NOT NULL,
    bot        boolean,
    username   varchar NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS users_serial_id_uindex ON users (serial_id);
CREATE UNIQUE INDEX IF NOT EXISTS users_user_id_uindex ON users (user_id);

-- Servers table (referenced by many other tables)
CREATE TABLE IF NOT EXISTS servers
(
    serial_id     serial,
    server_id     bigint NOT NULL
        CONSTRAINT servers_pk PRIMARY KEY,
    server_name   varchar,
    creation_date timestamp
);

CREATE UNIQUE INDEX IF NOT EXISTS servers_serial_id_uindex ON servers (serial_id);
CREATE UNIQUE INDEX IF NOT EXISTS servers_server_id_uindex ON servers (server_id);

-- Categories table
CREATE TABLE IF NOT EXISTS categories
(
    id         bigint NOT NULL
        CONSTRAINT categories_pk PRIMARY KEY,
    name       varchar,
    created_at timestamp,
    guild_id   bigint,
    position   integer,
    is_nsfw    boolean
);

CREATE UNIQUE INDEX IF NOT EXISTS categories_id_uindex ON categories (id);

-- Channels table
CREATE TABLE IF NOT EXISTS channels
(
    id          bigint NOT NULL
        CONSTRAINT channels_pk PRIMARY KEY,
    name        varchar,
    category_id bigint,
    created_at  timestamp,
    guild_id    bigint,
    position    integer,
    topic       varchar,
    is_nsfw     boolean,
    deleted     boolean DEFAULT false,
    allow_pins  boolean DEFAULT false NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS channels_id_uindex ON channels (id);

-- Roles table
CREATE TABLE IF NOT EXISTS roles
(
    id              bigint NOT NULL
        CONSTRAINT roles_pk PRIMARY KEY,
    name            varchar,
    color           varchar,
    created_at      timestamp,
    hoisted         boolean,
    managed         boolean,
    position        integer,
    guild_id        bigint
        CONSTRAINT roles_servers_server_id_fk REFERENCES servers,
    deleted         boolean DEFAULT false,
    self_assignable boolean DEFAULT false,
    weight          integer DEFAULT 0,
    alias           varchar,
    category        varchar DEFAULT 'Uncategorized'::character varying,
    required_roles  bigint[],
    auto_replace    boolean DEFAULT false NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS roles_id_uindex ON roles (id);
CREATE UNIQUE INDEX IF NOT EXISTS roles_guild_id_alias_uindex ON roles (guild_id, alias);

-- Threads table
CREATE TABLE IF NOT EXISTS threads
(
    id                    bigint NOT NULL
        CONSTRAINT threads_pk PRIMARY KEY,
    guild_id              bigint,
    parent_id             bigint,
    owner_id              bigint,
    slowmode_delay        integer,
    archived              boolean,
    locked                boolean,
    archiver_id           bigint,
    auto_archive_duration integer,
    is_private            boolean,
    name                  varchar,
    deleted               boolean
);

CREATE UNIQUE INDEX IF NOT EXISTS threads_id_uindex ON threads (id);

-- Poll table
CREATE TABLE IF NOT EXISTS poll
(
    api_url         varchar,
    poll_url        varchar,
    pinned_poll_id  bigint,
    channel_poll_id bigint,
    poll_update     boolean,
    expire_date     timestamp with time zone,
    id              bigint NOT NULL
        CONSTRAINT poll_pk PRIMARY KEY,
    start_date      timestamp with time zone,
    title           varchar,
    total_votes     integer,
    expired         boolean,
    num_options     integer,
    index_serial    integer DEFAULT nextval('poll_index_serial_seq'::regclass) NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS poll_id_uindex ON poll (id);
CREATE UNIQUE INDEX IF NOT EXISTS poll_index_serial_uindex ON poll (index_serial);

-- ============================================================================
-- PART 3: CREATE DEPENDENT TABLES (have foreign key references)
-- ============================================================================

-- Messages table (depends on users, servers)
CREATE TABLE IF NOT EXISTS messages
(
    message_id   bigint NOT NULL
        CONSTRAINT messages_pk PRIMARY KEY,
    created_at   timestamp NOT NULL,
    content      varchar,
    user_name    varchar,
    server_name  varchar NOT NULL,
    server_id    bigint NOT NULL
        CONSTRAINT messages_servers_server_id_fk REFERENCES servers,
    channel_id   bigint NOT NULL,
    channel_name varchar,
    user_id      bigint
        CONSTRAINT messages_users_user_id_fk REFERENCES users,
    user_nick    varchar,
    jump_url     varchar NOT NULL,
    is_bot       boolean NOT NULL,
    deleted      boolean DEFAULT false,
    reference    bigint
)
WITH (autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_cost_delay = 2);

CREATE UNIQUE INDEX IF NOT EXISTS messages_id_uindex ON messages (message_id);
CREATE INDEX IF NOT EXISTS messages_channel_id_index ON messages (channel_id DESC);
CREATE INDEX IF NOT EXISTS messages_message_id_channel_id_index ON messages (message_id DESC, channel_id ASC);
CREATE INDEX IF NOT EXISTS messages_created_at_index ON messages (created_at DESC);
CREATE INDEX IF NOT EXISTS messages_user_id_index ON messages (user_id);

-- Attachments table (depends on messages)
CREATE TABLE IF NOT EXISTS attachments
(
    id         bigint,
    filename   varchar,
    url        varchar,
    size       bigint,
    height     integer,
    width      integer,
    is_spoiler boolean,
    message_id bigint NOT NULL
);

-- Mentions table
CREATE TABLE IF NOT EXISTS mentions
(
    serial_id    serial
        CONSTRAINT mentions_pk PRIMARY KEY,
    message_id   bigint,
    user_mention bigint,
    role_mention bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS mentions_serial_id_uindex ON mentions (serial_id);

-- Reactions table
CREATE TABLE IF NOT EXISTS reactions
(
    unicode_emoji   varchar,
    message_id      bigint,
    user_id         bigint,
    emoji_name      varchar,
    animated        boolean,
    emoji_id        bigint,
    url             varchar,
    date            timestamp,
    removed         boolean DEFAULT false,
    id              serial
        CONSTRAINT reactions_pkey PRIMARY KEY,
    is_custom_emoji boolean
);

CREATE UNIQUE INDEX IF NOT EXISTS reactions_message_id_user_id_emoji_id_uindex
    ON reactions (message_id, user_id, emoji_id);
CREATE UNIQUE INDEX IF NOT EXISTS reactions_message_id_user_id_unicode_emoji_uindex
    ON reactions (message_id, user_id, unicode_emoji);

-- Infractions table (depends on users)
CREATE TABLE IF NOT EXISTS infractions
(
    id        integer DEFAULT nextval('infractions_id_seq'::regclass) NOT NULL
        CONSTRAINT infractions_pk PRIMARY KEY,
    user_id   bigint
        CONSTRAINT infractions_users_user_id_fk REFERENCES users,
    server_id bigint,
    date      timestamp,
    reason    varchar,
    severity  varchar
);

-- Server membership table (depends on users, servers)
CREATE TABLE IF NOT EXISTS server_membership
(
    serial_id serial,
    user_id   bigint
        CONSTRAINT server_membership_users_user_id_fk REFERENCES users,
    server_id bigint
        CONSTRAINT server_membership_servers_server_id_fk REFERENCES servers,
    CONSTRAINT server_membership_user_id_server_id_key UNIQUE (user_id, server_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS server_membership_serial_id_uindex ON server_membership (serial_id);
CREATE INDEX IF NOT EXISTS server_membership_server_id_user_id_index ON server_membership (server_id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS server_membership_user_id_server_id_uindex ON server_membership (user_id, server_id);

-- Role membership table (depends on users, roles)
CREATE TABLE IF NOT EXISTS role_membership
(
    user_id   bigint NOT NULL
        CONSTRAINT role_membership_users_user_id_fk REFERENCES users,
    role_id   bigint NOT NULL
        CONSTRAINT role_membership_roles_id_fk REFERENCES roles,
    serial_id serial
        CONSTRAINT role_membership_pk UNIQUE,
    CONSTRAINT role_membership_pk_2 PRIMARY KEY (user_id, role_id)
);

CREATE INDEX IF NOT EXISTS role_membership_role_id_user_id_index ON role_membership (role_id, user_id);
CREATE UNIQUE INDEX IF NOT EXISTS role_membership_serial_id_uindex ON role_membership (serial_id);
CREATE UNIQUE INDEX IF NOT EXISTS role_membership_user_id_role_id_uindex ON role_membership (user_id, role_id);

-- Role history table (depends on roles, users)
CREATE TABLE IF NOT EXISTS role_history
(
    serial_id serial
        CONSTRAINT role_history_pk PRIMARY KEY,
    role_id   bigint
        CONSTRAINT role_history_roles_id_fk REFERENCES roles,
    user_id   bigint
        CONSTRAINT role_history_users_user_id_fk REFERENCES users,
    gained    boolean DEFAULT true,
    date      timestamp
);

CREATE UNIQUE INDEX IF NOT EXISTS role_history_serial_id_uindex ON role_history (serial_id);

-- Thread membership table
CREATE TABLE IF NOT EXISTS thread_membership
(
    serial_id bigserial
        CONSTRAINT thread_membership_pk PRIMARY KEY,
    user_id   bigint,
    thread_id bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS thread_membership_serial_id_uindex ON thread_membership (serial_id);

-- Poll option table (depends on poll)
CREATE TABLE IF NOT EXISTS poll_option
(
    option_text varchar,
    poll_id     bigint
        CONSTRAINT foreign_key_name REFERENCES poll,
    num_votes   smallint,
    option_id   bigint NOT NULL
        CONSTRAINT poll_option_pk PRIMARY KEY,
    tokens      tsvector
);

CREATE UNIQUE INDEX IF NOT EXISTS index_name ON poll_option (option_id);

-- Command history table (depends on users, channels, servers)
CREATE TABLE IF NOT EXISTS command_history
(
    serial                serial
        CONSTRAINT command_history_pkey PRIMARY KEY,
    command_name          text,
    args                  json,
    start_date            timestamp NOT NULL,
    end_date              timestamp,
    run_time              interval,
    user_id               bigint NOT NULL
        CONSTRAINT command_history_user_id_fkey REFERENCES users,
    channel_id            bigint
        CONSTRAINT command_history_channel_id_fkey REFERENCES channels,
    guild_id              bigint
        CONSTRAINT command_history_guild_id_fkey REFERENCES servers,
    slash_command         boolean NOT NULL,
    started_successfully  boolean,
    finished_successfully boolean
);

CREATE INDEX IF NOT EXISTS index_date ON command_history (start_date);
CREATE INDEX IF NOT EXISTS index_user_id ON command_history (user_id);
CREATE INDEX IF NOT EXISTS index_guild_id ON command_history (guild_id);
CREATE INDEX IF NOT EXISTS index_channel_id ON command_history (channel_id);
CREATE INDEX IF NOT EXISTS index_command_name ON command_history (command_name);
CREATE INDEX IF NOT EXISTS index_finished_successfully ON command_history (finished_successfully);

-- Creator links table (depends on users)
CREATE TABLE IF NOT EXISTS creator_links
(
    serial_id    serial,
    user_id      bigint NOT NULL
        CONSTRAINT creator_links_users_user_id_fk REFERENCES users,
    title        varchar NOT NULL,
    link         varchar,
    nsfw         boolean DEFAULT false,
    last_changed timestamp DEFAULT now() NOT NULL,
    weight       integer DEFAULT 0,
    feature      boolean DEFAULT true NOT NULL,
    CONSTRAINT creator_links_pk PRIMARY KEY (user_id, title)
);

CREATE UNIQUE INDEX IF NOT EXISTS creator_links_serial_id_uindex ON creator_links (serial_id DESC);
CREATE INDEX IF NOT EXISTS creator_links_user_id_index ON creator_links (user_id);

-- Emotes table (depends on servers)
CREATE TABLE IF NOT EXISTS emotes
(
    serial_id      serial,
    guild_id       bigint
        CONSTRAINT emotes_servers_server_id_fk REFERENCES servers,
    emote_id       bigint NOT NULL
        CONSTRAINT emotes_pk PRIMARY KEY,
    name           varchar,
    user_id        bigint,
    created_at     timestamp,
    animated       boolean,
    available      boolean,
    managed        boolean,
    require_colons boolean,
    deleted        boolean DEFAULT false NOT NULL
);

-- ============================================================================
-- PART 4: STANDALONE TABLES (no foreign key dependencies)
-- ============================================================================

CREATE TABLE IF NOT EXISTS foliana_interlude
(
    serial_id     integer DEFAULT nextval('"foliana-interlude_serial_id_seq"'::regclass) NOT NULL,
    author        varchar,
    author_id     bigint,
    content       varchar,
    clean_content varchar,
    date          timestamp with time zone,
    message_id    bigint
);

CREATE TABLE IF NOT EXISTS gallery_mementos
(
    channel_name varchar NOT NULL
        CONSTRAINT gallery_mementos_pk PRIMARY KEY,
    channel_id   bigint NOT NULL,
    guild_id     bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS gallery_mementos_channel_name_uindex ON gallery_mementos (channel_name);

CREATE TABLE IF NOT EXISTS invisible_text_twi
(
    serial_id  integer DEFAULT nextval('invisible_text_twi_serial_id_seq'::regclass) NOT NULL,
    content    varchar,
    chapter_id varchar,
    title      varchar,
    date       timestamp with time zone
);

CREATE TABLE IF NOT EXISTS join_leave
(
    user_id       bigint,
    date          timestamp,
    join_or_leave varchar,
    server_name   varchar,
    server_id     bigint,
    created_at    timestamp,
    id            serial
        CONSTRAINT join_leave_pkey PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS password_link
(
    serial_id serial,
    password  varchar,
    link      varchar,
    user_id   bigint,
    date      timestamp with time zone
);

CREATE TABLE IF NOT EXISTS patreon_twi
(
    serial_id                 integer DEFAULT nextval('patreon_twi_serial_id_seq'::regclass) NOT NULL,
    post_id                   integer,
    title                     varchar,
    content                   varchar,
    comment_count             integer,
    like_count                integer,
    url                       varchar,
    min_cents_pledged_to_view integer,
    post_type                 varchar,
    published_at              timestamp with time zone,
    image                     varchar,
    password                  varchar,
    body                      jsonb
);

CREATE UNIQUE INDEX IF NOT EXISTS patreon_twi_post_id_uindex ON patreon_twi (post_id);
CREATE UNIQUE INDEX IF NOT EXISTS patreon_twi_url_uindex ON patreon_twi (url);

CREATE TABLE IF NOT EXISTS protected_is_public
(
    serial_id integer DEFAULT nextval('protected_is_public_serial_id_seq'::regclass) NOT NULL,
    url       varchar,
    title     varchar
);

CREATE TABLE IF NOT EXISTS quotes
(
    serial_id serial,
    quote     varchar,
    author    varchar,
    author_id bigint,
    time      timestamp with time zone,
    tokens    tsvector
);

CREATE TABLE IF NOT EXISTS links
(
    id                integer DEFAULT nextval('tags_id_seq'::regclass) NOT NULL,
    content           varchar,
    tag               varchar,
    user_who_added    varchar,
    id_user_who_added bigint,
    time_added        timestamp with time zone,
    title             varchar,
    embed             boolean,
    guild_id          bigint
);

CREATE UNIQUE INDEX IF NOT EXISTS tags_title_uindex ON links (title);

CREATE TABLE IF NOT EXISTS wandering_inn
(
    serial_id             integer DEFAULT nextval('wandering_inn_serial_id_seq'::regclass) NOT NULL
        CONSTRAINT wandering_inn_pk PRIMARY KEY,
    title                 varchar,
    content_post_clean    varchar,
    content_post          varchar,
    content_all           varchar,
    date                  timestamp with time zone,
    link                  varchar,
    word_count            integer,
    table_of_content_link varchar,
    volume                smallint,
    invisible_text        varchar,
    id                    varchar
);

CREATE TABLE IF NOT EXISTS webhook_pins_twi
(
    serial_id   integer DEFAULT nextval('webhook_pins_twi_serial_id_seq'::regclass) NOT NULL,
    message_id  bigint,
    webhook_id  bigint,
    posted_date timestamp with time zone
);

CREATE TABLE IF NOT EXISTS twi_reddit
(
    serial_index     serial,
    time_added       timestamp NOT NULL,
    discord_username varchar,
    discord_id       bigint NOT NULL
        CONSTRAINT twi_reddit_pk PRIMARY KEY,
    reddit_username  varchar NOT NULL,
    currant_patreon  boolean NOT NULL,
    subreddit        varchar NOT NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS twi_reddit_discord_id_uindex ON twi_reddit (discord_id);
CREATE UNIQUE INDEX IF NOT EXISTS twi_reddit_serial_index_uindex ON twi_reddit (serial_index);
CREATE UNIQUE INDEX IF NOT EXISTS twi_reddit_reddit_username_uindex ON twi_reddit (reddit_username);

CREATE TABLE IF NOT EXISTS updates
(
    serial_id     serial
        CONSTRAINT updates_pk PRIMARY KEY,
    updated_table varchar,
    action        varchar,
    before        varchar,
    after         varchar,
    date          timestamp,
    primary_key   varchar
);

CREATE UNIQUE INDEX IF NOT EXISTS updates_serial_id_uindex ON updates (serial_id);

CREATE TABLE IF NOT EXISTS message_edit
(
    serial_id      serial
        CONSTRAINT message_edit_pk PRIMARY KEY,
    id             bigint,
    old_content    varchar,
    new_content    varchar,
    edit_timestamp timestamp
);

CREATE UNIQUE INDEX IF NOT EXISTS message_edit_serial_id_uindex ON message_edit (serial_id);

CREATE TABLE IF NOT EXISTS banned_words
(
    serial_id       serial,
    word            varchar,
    patreon_allowed boolean,
    server          bigint,
    comment         varchar
);

CREATE UNIQUE INDEX IF NOT EXISTS banned_words_serial_id_uindex ON banned_words (serial_id);
CREATE UNIQUE INDEX IF NOT EXISTS banned_words_word_uindex ON banned_words (word);

CREATE TABLE IF NOT EXISTS button_action_history
(
    serial    serial,
    user_id   bigint NOT NULL,
    view_id   bigint NOT NULL,
    guild_id  bigint,
    date      timestamp,
    button_id integer,
    CONSTRAINT button_action_history_pk PRIMARY KEY (user_id, view_id)
);

CREATE TABLE IF NOT EXISTS innktober_quests
(
    serial     serial
        CONSTRAINT innktober_quests_pk PRIMARY KEY,
    quest_name varchar,
    nsfw       boolean,
    thread_id  bigint
);

CREATE TABLE IF NOT EXISTS innktober_submission
(
    id                            serial
        CONSTRAINT innktober_submission_pk PRIMARY KEY,
    user_id                       bigint,
    date                          timestamp with time zone,
    message_id                    bigint,
    quest_id                      varchar,
    repost_message_id             bigint,
    social_media_consent          boolean,
    wiki_booru_consent            boolean,
    submission_type               varchar,
    approved                      boolean,
    approval_date                 timestamp with time zone,
    approved_by                   bigint,
    social_media_approved_post_id bigint,
    booru_wiki_approved_post_id   bigint,
    channel_id                    bigint
);

CREATE TABLE IF NOT EXISTS bot_metrics
(
    id          serial
        CONSTRAINT bot_metrics_pk PRIMARY KEY,
    timestamp   timestamp NOT NULL DEFAULT now(),
    metric_type varchar NOT NULL,
    metric_data json
);

CREATE INDEX IF NOT EXISTS bot_metrics_timestamp_index ON bot_metrics (timestamp);
CREATE INDEX IF NOT EXISTS bot_metrics_metric_type_index ON bot_metrics (metric_type);

-- ============================================================================
-- PART 5: ERROR TELEMETRY TABLE (for error tracking)
-- ============================================================================

CREATE TABLE IF NOT EXISTS error_telemetry
(
    id            serial PRIMARY KEY,
    error_type    varchar NOT NULL,
    command_name  varchar,
    user_id       bigint,
    error_message text,
    guild_id      bigint,
    channel_id    bigint,
    timestamp     timestamp NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS error_telemetry_timestamp_index ON error_telemetry (timestamp);
CREATE INDEX IF NOT EXISTS error_telemetry_error_type_index ON error_telemetry (error_type);
CREATE INDEX IF NOT EXISTS error_telemetry_command_name_index ON error_telemetry (command_name);

-- ============================================================================
-- PART 6: GRANT PERMISSIONS (if needed)
-- ============================================================================
-- Uncomment and modify if you need to grant permissions to a specific user
-- GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO your_user;
-- GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO your_user;

-- ============================================================================
-- INITIALIZATION COMPLETE
-- ============================================================================
SELECT 'Database initialization complete. Created all tables, sequences, and indexes.' AS status;
