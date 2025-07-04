create table attachments
(
    id         bigint,
    filename   varchar,
    url        varchar,
    size       bigint,
    height     integer,
    width      integer,
    is_spoiler boolean,
    message_id bigint not null
);

create table foliana_interlude
(
    serial_id     integer default nextval('"foliana-interlude_serial_id_seq"'::regclass) not null,
    author        varchar,
    author_id     bigint,
    content       varchar,
    clean_content varchar,
    date          timestamp with time zone,
    message_id    bigint
);

create table gallery_mementos
(
    channel_name varchar not null
        constraint gallery_mementos_pk
            primary key,
    channel_id   bigint  not null,
    guild_id     bigint
);

create unique index gallery_mementos_channel_name_uindex
    on gallery_mementos (channel_name);

create table invisible_text_twi
(
    serial_id  integer default nextval('invisible_text_twi_serial_id_seq'::regclass) not null,
    content    varchar,
    chapter_id varchar,
    title      varchar,
    date       timestamp with time zone
);

create table join_leave
(
    user_id       bigint,
    date          timestamp,
    join_or_leave varchar,
    server_name   varchar,
    server_id     bigint,
    created_at    timestamp,
    id            serial
        constraint join_leave_pkey
            primary key
);

create table password_link
(
    serial_id serial,
    password  varchar,
    link      varchar,
    user_id   bigint,
    date      timestamp with time zone
);

create table patreon_twi
(
    serial_id                 integer default nextval('patreon_twi_serial_id_seq'::regclass) not null,
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

create unique index patreon_twi_post_id_uindex
    on patreon_twi (post_id);

create unique index patreon_twi_url_uindex
    on patreon_twi (url);

create table poll
(
    api_url         varchar,
    poll_url        varchar,
    pinned_poll_id  bigint,
    channel_poll_id bigint,
    poll_update     boolean,
    expire_date     timestamp with time zone,
    id              bigint                                                     not null
        constraint poll_pk
            primary key,
    start_date      timestamp with time zone,
    title           varchar,
    total_votes     integer,
    expired         boolean,
    num_options     integer,
    index_serial    integer default nextval('poll_index_serial_seq'::regclass) not null
);

create unique index poll_id_uindex
    on poll (id);

create unique index poll_index_serial_uindex
    on poll (index_serial);

create table poll_option
(
    option_text varchar,
    poll_id     bigint
        constraint foreign_key_name
            references poll,
    num_votes   smallint,
    option_id   bigint not null
        constraint poll_option_pk
            primary key,
    tokens      tsvector
);

create unique index index_name
    on poll_option (option_id);

create table protected_is_public
(
    serial_id integer default nextval('protected_is_public_serial_id_seq'::regclass) not null,
    url       varchar,
    title     varchar
);

create table quotes
(
    serial_id serial,
    quote     varchar,
    author    varchar,
    author_id bigint,
    time      timestamp with time zone,
    tokens    tsvector
);

create table reactions
(
    unicode_emoji   varchar,
    message_id      bigint,
    user_id         bigint,
    emoji_name      varchar,
    animated        boolean,
    emoji_id        bigint,
    url             varchar,
    date            timestamp,
    removed         boolean default false,
    id              serial
        constraint reactions_pkey
            primary key,
    is_custom_emoji boolean
);

create unique index reactions_message_id_user_id_emoji_id_uindex
    on reactions (message_id, user_id, emoji_id);

create unique index reactions_message_id_user_id_unicode_emoji_uindex
    on reactions (message_id, user_id, unicode_emoji);

create table links
(
    id                integer default nextval('tags_id_seq'::regclass) not null,
    content           varchar,
    tag               varchar,
    user_who_added    varchar,
    id_user_who_added bigint,
    time_added        timestamp with time zone,
    title             varchar,
    embed             boolean,
    guild_id          bigint
);

create unique index tags_title_uindex
    on links (title);

create table wandering_inn
(
    serial_id             integer default nextval('wandering_inn_serial_id_seq'::regclass) not null
        constraint wandering_inn_pk
            primary key,
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

create table webhook_pins_twi
(
    serial_id   integer default nextval('webhook_pins_twi_serial_id_seq'::regclass) not null,
    message_id  bigint,
    webhook_id  bigint,
    posted_date timestamp with time zone
);

create table twi_reddit
(
    serial_index     serial,
    time_added       timestamp not null,
    discord_username varchar,
    discord_id       bigint    not null
        constraint twi_reddit_pk
            primary key,
    reddit_username  varchar   not null,
    currant_patreon  boolean   not null,
    subreddit        varchar   not null
);

create unique index twi_reddit_discord_id_uindex
    on twi_reddit (discord_id);

create unique index twi_reddit_serial_index_uindex
    on twi_reddit (serial_index);

create unique index twi_reddit_reddit_username_uindex
    on twi_reddit (reddit_username);

create table users
(
    serial_id  serial,
    user_id    bigint                                                               not null
        constraint users_pk
            primary key,
    created_at timestamp default '1970-01-01 00:00:00'::timestamp without time zone not null,
    bot        boolean,
    username   varchar                                                              not null
);

create unique index users_serial_id_uindex
    on users (serial_id);

create unique index users_user_id_uindex
    on users (user_id);

create table infractions
(
    id        integer default nextval('infractions_id_seq'::regclass) not null
        constraint infractions_pk
            primary key,
    user_id   bigint
        constraint infractions_users_user_id_fk
            references users,
    server_id bigint,
    date      timestamp,
    reason    varchar,
    severity  varchar
);

create table servers
(
    serial_id     serial,
    server_id     bigint not null
        constraint servers_pk
            primary key,
    server_name   varchar,
    creation_date timestamp
);

create table messages
(
    message_id   bigint    not null
        constraint messages_pk
            primary key,
    created_at   timestamp not null,
    content      varchar,
    user_name    varchar,
    server_name  varchar   not null,
    server_id    bigint    not null
        constraint messages_servers_server_id_fk
            references servers,
    channel_id   bigint    not null,
    channel_name varchar,
    user_id      bigint
        constraint messages_users_user_id_fk
            references users,
    user_nick    varchar,
    jump_url     varchar   not null,
    is_bot       boolean   not null,
    deleted      boolean default false,
    reference    bigint
)
    with (autovacuum_vacuum_scale_factor = 0.05, autovacuum_vacuum_cost_delay = 2);

create unique index messages_id_uindex
    on messages (message_id);

create index messages_channel_id_index
    on messages (channel_id desc);

create index messages_message_id_channel_id_index
    on messages (message_id desc, channel_id asc);

create index messages_created_at_index
    on messages (created_at desc);

create index messages_user_id_index
    on messages (user_id);

create unique index servers_serial_id_uindex
    on servers (serial_id);

create unique index servers_server_id_uindex
    on servers (server_id);

create table server_membership
(
    serial_id serial,
    user_id   bigint
        constraint server_membership_users_user_id_fk
            references users,
    server_id bigint
        constraint server_membership_servers_server_id_fk
            references servers,
    constraint server_membership_user_id_server_id_key
        unique (user_id, server_id)
);

create unique index server_membership_serial_id_uindex
    on server_membership (serial_id);

create index server_membership_server_id_user_id_index
    on server_membership (server_id, user_id);

create unique index server_membership_user_id_server_id_uindex
    on server_membership (user_id, server_id);

create table mentions
(
    serial_id    serial
        constraint mentions_pk
            primary key,
    message_id   bigint,
    user_mention bigint,
    role_mention bigint
);

create unique index mentions_serial_id_uindex
    on mentions (serial_id);

create table roles
(
    id              bigint                not null
        constraint roles_pk
            primary key,
    name            varchar,
    color           varchar,
    created_at      timestamp,
    hoisted         boolean,
    managed         boolean,
    position        integer,
    guild_id        bigint
        constraint roles_servers_server_id_fk
            references servers,
    deleted         boolean default false,
    self_assignable boolean default false,
    weight          integer default 0,
    alias           varchar,
    category        varchar default 'Uncategorized'::character varying,
    required_roles  bigint[],
    auto_replace    boolean default false not null
);

create unique index roles_id_uindex
    on roles (id);

create unique index roles_guild_id_alias_uindex
    on roles (guild_id, alias);

create table channels
(
    id          bigint                not null
        constraint channels_pk
            primary key,
    name        varchar,
    category_id bigint,
    created_at  timestamp,
    guild_id    bigint,
    position    integer,
    topic       varchar,
    is_nsfw     boolean,
    deleted     boolean default false,
    allow_pins  boolean default false not null
);

create unique index channels_id_uindex
    on channels (id);

create table categories
(
    id         bigint not null
        constraint categories_pk
            primary key,
    name       varchar,
    created_at timestamp,
    guild_id   bigint,
    position   integer,
    is_nsfw    boolean
);

create unique index categories_id_uindex
    on categories (id);

create table role_membership
(
    user_id   bigint not null
        constraint role_membership_users_user_id_fk
            references users,
    role_id   bigint not null
        constraint role_membership_roles_id_fk
            references roles,
    serial_id serial
        constraint role_membership_pk
            unique,
    constraint role_membership_pk_2
        primary key (user_id, role_id)
);

create index role_membership_role_id_user_id_index
    on role_membership (role_id, user_id);

create unique index role_membership_serial_id_uindex
    on role_membership (serial_id);

create unique index role_membership_user_id_role_id_uindex
    on role_membership (user_id, role_id);

create table updates
(
    serial_id     serial
        constraint updates_pk
            primary key,
    updated_table varchar,
    action        varchar,
    before        varchar,
    after         varchar,
    date          timestamp,
    primary_key   varchar
);

create unique index updates_serial_id_uindex
    on updates (serial_id);

create table role_history
(
    serial_id serial
        constraint role_history_pk
            primary key,
    role_id   bigint
        constraint role_history_roles_id_fk
            references roles,
    user_id   bigint
        constraint role_history_users_user_id_fk
            references users,
    gained    boolean default true,
    date      timestamp
);

create unique index role_history_serial_id_uindex
    on role_history (serial_id);

create table threads
(
    id                    bigint not null
        constraint threads_pk
            primary key,
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

create unique index threads_id_uindex
    on threads (id);

create table thread_membership
(
    serial_id bigserial
        constraint thread_membership_pk
            primary key,
    user_id   bigint,
    thread_id bigint
);

create unique index thread_membership_serial_id_uindex
    on thread_membership (serial_id);

create table message_edit
(
    serial_id      serial
        constraint message_edit_pk
            primary key,
    id             bigint,
    old_content    varchar,
    new_content    varchar,
    edit_timestamp timestamp
);

create unique index message_edit_serial_id_uindex
    on message_edit (serial_id);

create table banned_words
(
    serial_id       serial,
    word            varchar,
    patreon_allowed boolean,
    server          bigint,
    comment         varchar
);

create unique index banned_words_serial_id_uindex
    on banned_words (serial_id);

create unique index banned_words_word_uindex
    on banned_words (word);

create table creator_links
(
    serial_id    serial,
    user_id      bigint                  not null
        constraint creator_links_users_user_id_fk
            references users,
    title        varchar                 not null,
    link         varchar,
    nsfw         boolean   default false,
    last_changed timestamp default now() not null,
    weight       integer   default 0,
    feature      boolean   default true  not null,
    constraint creator_links_pk
        primary key (user_id, title)
);

create unique index creator_links_serial_id_uindex
    on creator_links (serial_id desc);

create index creator_links_user_id_index
    on creator_links (user_id);

create table button_action_history
(
    serial    serial,
    user_id   bigint not null,
    view_id   bigint not null,
    guild_id  bigint,
    date      timestamp,
    button_id integer,
    constraint button_action_history_pk
        primary key (user_id, view_id)
);

create table command_history
(
    serial                serial
        constraint command_history_pkey
            primary key,
    command_name          text,
    args                  json,
    start_date            timestamp not null,
    end_date              timestamp,
    run_time              interval,
    user_id               bigint    not null
        constraint command_history_user_id_fkey
            references users,
    channel_id            bigint
        constraint command_history_channel_id_fkey
            references channels,
    guild_id              bigint
        constraint command_history_guild_id_fkey
            references servers,
    slash_command         boolean   not null,
    started_successfully  boolean,
    finished_successfully boolean
);

create index index_date
    on command_history (start_date);

create index index_user_id
    on command_history (user_id);

create index index_guild_id
    on command_history (guild_id);

create index index_channel_id
    on command_history (channel_id);

create index index_command_name
    on command_history (command_name);

create index index_finished_successfully
    on command_history (finished_successfully);

create table emotes
(
    serial_id      serial,
    guild_id       bigint
        constraint emotes_servers_server_id_fk
            references servers,
    emote_id       bigint                not null
        constraint emotes_pk
            primary key,
    name           varchar,
    user_id        bigint,
    created_at     timestamp,
    animated       boolean,
    available      boolean,
    managed        boolean,
    require_colons boolean,
    deleted        boolean default false not null
);

create table innktober_quests
(
    serial     serial
        constraint innktober_quests_pk
            primary key,
    quest_name varchar,
    nsfw       boolean,
    thread_id  bigint
);

create table innktober_submission
(
    id                            serial
        constraint innktober_submission_pk
            primary key,
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

create table bot_metrics
(
    id          serial
        constraint bot_metrics_pk
            primary key,
    timestamp   timestamp not null default now(),
    metric_type varchar not null,
    metric_data json
);

create index bot_metrics_timestamp_index
    on bot_metrics (timestamp);

create index bot_metrics_metric_type_index
    on bot_metrics (metric_type);
