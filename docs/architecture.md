# Twi Bot Shard Architecture Documentation

This document provides an overview of the Twi Bot Shard architecture, including component diagrams, design decisions, and architectural patterns used throughout the project.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Diagrams](#architecture-diagrams)
   - [High-Level Architecture](#high-level-architecture)
   - [Component Diagram](#component-diagram)
   - [Database Schema](#database-schema)
   - [Command Flow](#command-flow)
3. [Design Decisions](#design-decisions)
   - [Technology Choices](#technology-choices)
   - [Architectural Patterns](#architectural-patterns)
   - [Database Design](#database-design)
   - [Error Handling Strategy](#error-handling-strategy)
4. [Component Details](#component-details)
   - [Bot Core](#bot-core)
   - [Command Handlers](#command-handlers)
   - [Database Access Layer](#database-access-layer)
   - [External Service Integrations](#external-service-integrations)
   - [Utility Services](#utility-services)

## System Overview

Twi Bot Shard is a Discord bot built using discord.py that provides moderation, utility, and content management features for Discord servers. The bot is designed with a modular architecture that separates concerns and allows for easy extension and maintenance.

The system consists of the following major components:

1. **Bot Core**: Handles Discord events, command registration, and lifecycle management
2. **Command Handlers (Cogs)**: Implement specific bot features and commands
3. **Database Access Layer**: Provides abstraction for database operations
4. **External Service Integrations**: Connects to third-party services like Twitter, DeviantArt, etc.
5. **Utility Services**: Provides shared functionality like validation, error handling, and logging

## Architecture Diagrams

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Discord Platform                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                          Twi Bot Shard                           │
│                                                                  │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │   Bot Core   │◄──►│    Cogs     │◄──►│  Service Container  │  │
│  └─────────────┘    └─────────────┘    └─────────┬───────────┘  │
│                                                   │              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────▼───────────┐  │
│  │   Logging   │◄──►│ Error Handler│◄──►│  Database Service   │  │
│  └─────────────┘    └─────────────┘    └─────────┬───────────┘  │
│                                                   │              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────▼───────────┐  │
│  │ Validation  │◄──►│  Utilities   │◄──►│ External Services   │  │
│  └─────────────┘    └─────────────┘    └─────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        PostgreSQL Database                       │
└─────────────────────────────────────────────────────────────────┘
```

### Component Diagram

```
┌───────────────────────────────────────────────────────────────────────┐
│                              main.py                                   │
│                                                                        │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐    │
│  │  Bot Instance   │  │ Command Registry │  │ Event Dispatching   │    │
│  └────────┬────────┘  └────────┬────────┘  └──────────┬──────────┘    │
└───────────┼─────────────────────┼─────────────────────┼────────────────┘
            │                     │                     │
            ▼                     ▼                     ▼
┌───────────────────────────────────────────────────────────────────────┐
│                                Cogs                                    │
│                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │  Moderation │  │   Utility   │  │   Gallery   │  │    Other    │   │
│  └─────┬───────┘  └─────┬───────┘  └─────┬───────┘  └─────┬───────┘   │
└────────┼─────────────────┼─────────────────┼─────────────────┼─────────┘
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
┌───────────────────────────────────────────────────────────────────────┐
│                          Service Container                             │
│                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │     DB      │  │   Logging   │  │   Cache     │  │   Config    │   │
│  └─────┬───────┘  └─────┬───────┘  └─────┬───────┘  └─────┬───────┘   │
└────────┼─────────────────┼─────────────────┼─────────────────┼─────────┘
         │                 │                 │                 │
         ▼                 ▼                 ▼                 ▼
┌───────────────────────────────────────────────────────────────────────┐
│                             Utilities                                  │
│                                                                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐   │
│  │ Validation  │  │Error Handling│  │ Permissions │  │  Security   │   │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘   │
└───────────────────────────────────────────────────────────────────────┘
```

### Database Schema

```
┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│    servers    │       │     users     │       │   commands    │
├───────────────┤       ├───────────────┤       ├───────────────┤
│ id            │       │ id            │       │ id            │
│ server_id     │       │ user_id       │       │ name          │
│ prefix        │       │ username      │       │ description   │
│ settings      │       │ joined_at     │       │ usage_count   │
└───────┬───────┘       └───────┬───────┘       └───────────────┘
        │                       │
        │                       │
┌───────▼───────┐       ┌───────▼───────┐       ┌───────────────┐
│  server_stats  │       │   user_stats  │       │    gallery    │
├───────────────┤       ├───────────────┤       ├───────────────┤
│ server_id     │       │ user_id       │       │ id            │
│ message_count │       │ message_count │       │ title         │
│ member_count  │       │ command_count │       │ url           │
│ command_count │       │ last_active   │       │ description   │
└───────────────┘       └───────────────┘       │ added_by      │
                                                │ added_at      │
                                                └───────────────┘

┌───────────────┐       ┌───────────────┐       ┌───────────────┐
│ creator_links │       │  error_logs   │       │  audit_logs   │
├───────────────┤       ├───────────────┤       ├───────────────┤
│ id            │       │ id            │       │ id            │
│ platform      │       │ error_type    │       │ user_id       │
│ username      │       │ message       │       │ action        │
│ url           │       │ command       │       │ timestamp     │
│ added_by      │       │ user_id       │       │ details       │
│ added_at      │       │ timestamp     │       └───────────────┘
└───────────────┘       └───────────────┘
```

### Command Flow

```
┌──────────┐     ┌──────────┐     ┌──────────┐     ┌──────────┐
│  Discord │     │  Bot     │     │  Command │     │ Database │
│  Event   │────►│  Core    │────►│  Handler │────►│  Service │
└──────────┘     └──────────┘     └──────────┘     └──────────┘
                      │                │                │
                      │                │                │
                      ▼                ▼                ▼
                 ┌──────────┐     ┌──────────┐     ┌──────────┐
                 │Permission│     │ Response │     │  Logging │
                 │  Check   │     │ Formatter│     │  Service │
                 └──────────┘     └──────────┘     └──────────┘
```

## Design Decisions

### Technology Choices

#### Discord.py

We chose discord.py as our primary framework for several reasons:

1. **Mature Ecosystem**: discord.py is a well-established library with extensive documentation and community support.
2. **Async Support**: Built on Python's asyncio, it provides efficient handling of Discord's real-time events.
3. **Feature Completeness**: Supports all Discord API features we need, including slash commands.
4. **Extensibility**: The Cog system allows for modular organization of commands and features.

#### PostgreSQL

PostgreSQL was selected as our database for the following reasons:

1. **Reliability**: PostgreSQL is known for its reliability and data integrity.
2. **JSON Support**: Native JSONB support for flexible data storage.
3. **Scalability**: Handles large datasets efficiently with good indexing options.
4. **Async Support**: Works well with asyncpg for asynchronous database operations.

#### SQLAlchemy ORM

We transitioned to SQLAlchemy ORM for these reasons:

1. **Type Safety**: Provides type-safe database operations.
2. **Code Maintainability**: Reduces boilerplate and improves code readability.
3. **Migration Support**: Works well with Alembic for database migrations.
4. **Query Building**: Offers a powerful query building API.

### Architectural Patterns

#### Dependency Injection

We implemented a dependency injection pattern using a service container to:

1. **Decouple Components**: Reduce direct dependencies between components.
2. **Improve Testability**: Make it easier to mock dependencies in tests.
3. **Centralize Configuration**: Manage service configuration in one place.
4. **Lifecycle Management**: Control the lifecycle of service instances.

#### Repository Pattern

For database access, we use the repository pattern to:

1. **Abstract Data Access**: Hide database implementation details.
2. **Centralize Queries**: Keep related queries together.
3. **Simplify Testing**: Make it easier to mock database operations.
4. **Enforce Business Rules**: Apply domain logic consistently.

#### Command Pattern

Discord.py's command system implements the command pattern, which we leverage to:

1. **Encapsulate Actions**: Each command encapsulates a specific action.
2. **Decouple Invocation**: Separate command invocation from execution.
3. **Support Undo/Redo**: Enable command history and reversal where appropriate.
4. **Extend Functionality**: Add middleware like permission checks and error handling.

### Database Design

#### Schema Design Principles

1. **Normalization**: Tables are normalized to reduce redundancy.
2. **Indexing Strategy**: Frequently queried columns are indexed.
3. **Foreign Keys**: Relationships are enforced with foreign key constraints.
4. **Soft Deletes**: Records are marked as deleted rather than removed.

#### Query Optimization

1. **Prepared Statements**: All queries use prepared statements for security and performance.
2. **Connection Pooling**: Database connections are pooled for efficiency.
3. **Query Caching**: Frequently used queries are cached.
4. **Pagination**: Large result sets are paginated to reduce memory usage.

### Error Handling Strategy

We implemented a comprehensive error handling strategy with these principles:

1. **Centralized Handling**: Global error handlers catch and process all exceptions.
2. **User-Friendly Messages**: Error messages are sanitized and user-friendly.
3. **Detailed Logging**: Errors are logged with context for debugging.
4. **Error Telemetry**: Error patterns are tracked for proactive resolution.
5. **Security Focus**: Sensitive information is redacted from error messages.

## Component Details

### Bot Core

The bot core (main.py) is responsible for:

1. **Initialization**: Setting up the bot instance and dependencies.
2. **Command Registration**: Loading cogs and registering commands.
3. **Event Handling**: Setting up global event handlers.
4. **Error Management**: Configuring global error handlers.
5. **Lifecycle Management**: Handling startup, shutdown, and reconnection.

### Command Handlers

Command handlers (cogs) implement specific bot features:

1. **Moderation Cogs**: User and message management commands.
2. **Utility Cogs**: General-purpose utility commands.
3. **Content Cogs**: Gallery and creator link management.
4. **Statistics Cogs**: Server and user statistics tracking.
5. **Configuration Cogs**: Bot settings and customization.

### Database Access Layer

The database layer consists of:

1. **Database Service**: Manages database connections and transactions.
2. **Repositories**: Implement data access for specific entities.
3. **Models**: Define the structure of database entities.
4. **Query Cache**: Caches frequently used query results.
5. **Migrations**: Handles database schema changes.

### External Service Integrations

External service integrations include:

1. **Twitter API**: For fetching tweets and monitoring accounts.
2. **DeviantArt API**: For gallery integration.
3. **AO3 API**: For story updates and notifications.
4. **OpenAI API**: For content summarization.
5. **Google API**: For search functionality.

### Utility Services

Utility services provide shared functionality:

1. **Validation**: Input validation and sanitization.
2. **Error Handling**: Standardized error processing.
3. **Logging**: Structured logging and telemetry.
4. **Permissions**: Role-based access control.
5. **Security**: Credential management and security features.