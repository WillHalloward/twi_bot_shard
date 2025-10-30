# Twi Bot Shard (Cognita) Documentation

Welcome to the Twi Bot Shard documentation! This is your central hub for all documentation related to the Discord bot.

## Quick Links

- **🚀 [Getting Started](developer/getting-started.md)** - Set up your development environment
- **📖 [User Guide](user/getting-started.md)** - Learn how to use the bot
- **🏗️ [Architecture](developer/architecture/overview.md)** - Understand the system design
- **🚢 [Deployment](operations/deployment/production.md)** - Deploy to production
- **🤝 [Contributing](meta/contributing.md)** - Contribute to the project

## Documentation by Audience

### 👥 For Users

If you're using the bot in your Discord server:

- **[Getting Started](user/getting-started.md)** - Quick start guide
- **[Commands](user/commands/)** - All available commands
  - [Moderation Commands](user/commands/moderation.md)
  - [Utility Commands](user/commands/utility.md)
  - [TWI-Specific Commands](user/commands/twi-specific.md)
  - [Gallery Commands](user/commands/gallery.md)
  - [Statistics Commands](user/commands/stats.md)
- **[Features](user/features.md)** - Detailed feature descriptions
- **[Troubleshooting](user/troubleshooting.md)** - Common issues and solutions

### 💻 For Developers

If you're developing or contributing to the bot:

#### Getting Started
- **[Developer Setup](developer/getting-started.md)** - Complete setup guide
- **[Environment Variables](developer/setup/environment-variables.md)** - Configuration reference
- **[Database Setup](developer/setup/database-setup.md)** - Database configuration

#### Architecture
- **[Overview](developer/architecture/overview.md)** - System architecture
- **[Cog System](developer/architecture/cog-system.md)** - Understanding cogs
- **[Database Layer](developer/architecture/database-layer.md)** - Database architecture
- **[Dependency Injection](developer/architecture/dependency-injection.md)** - DI patterns
- **[Error Handling](developer/architecture/error-handling.md)** - Error handling system

#### How-To Guides
- **[Creating Cogs](developer/guides/creating-cogs.md)** - Build new features
- **[Adding Commands](developer/guides/adding-commands.md)** - Create commands
- **[Database Operations](developer/guides/database-operations.md)** - Work with the database
- **[Testing](developer/guides/testing.md)** - Write and run tests
- **[Debugging](developer/guides/debugging.md)** - Debug issues

#### Reference
- **[API Reference](developer/reference/api.md)** - Complete API documentation
- **[Cog Reference](developer/reference/cogs.md)** - All cogs documented
- **[Database Schema](developer/reference/database-schema.md)** - Schema reference
- **[Configuration](developer/reference/configuration.md)** - Config options

#### Advanced Topics
- **[Performance](developer/advanced/performance.md)** - Optimization techniques
- **[Caching](developer/advanced/caching.md)** - Caching strategies
- **[Monitoring](developer/advanced/monitoring.md)** - Monitoring and alerting
- **[Security](developer/advanced/security.md)** - Security best practices
- **[Property-Based Testing](developer/advanced/property-based-testing.md)** - Advanced testing

### 🚀 For Operations

If you're deploying or maintaining the bot:

#### Deployment
- **[Local Deployment](operations/deployment/local.md)** - Run locally
- **[Production Deployment](operations/deployment/production.md)** - Production setup
- **[Docker Deployment](operations/deployment/docker.md)** - Containerized deployment

#### Database Operations
- **[Migrations](operations/database/migrations.md)** - Schema migrations
- **[Optimizations](operations/database/optimizations.md)** - Performance tuning
- **[Backup & Recovery](operations/database/backup-recovery.md)** - Data protection
- **[Best Practices](operations/database/best-practices.md)** - Operational guidelines

#### Monitoring & Maintenance
- **[Monitoring](operations/monitoring.md)** - System monitoring
- **[Maintenance](operations/maintenance.md)** - Regular maintenance tasks

### 📚 Meta Documentation

Project documentation and guidelines:

- **[Contributing Guide](meta/contributing.md)** - How to contribute
- **[Documentation Guide](meta/documentation-guide.md)** - Writing docs
- **[Changelog](meta/changelog.md)** - Version history
- **[Archived Docs](meta/archived/)** - Historical documentation

## Project Information

### What is Twi Bot Shard (Cognita)?

Twi Bot Shard is a feature-rich Discord bot built for "The Wandering Inn" community. It provides:

- **Statistics Tracking** - Message counts, user activity, server trends
- **Content Reposting** - Gallery system for community art and content
- **TWI-Specific Features** - Schedule tracking, wiki integration, notifications
- **Moderation Tools** - Server management and administration
- **Utility Commands** - Helpful tools for users and moderators

### Technology Stack

- **Language**: Python 3.12
- **Framework**: discord.py (async)
- **Database**: PostgreSQL with asyncpg
- **ORM**: SQLAlchemy 2.0
- **Architecture**: Modular cog system with dependency injection
- **Patterns**: Repository pattern, service container, event-driven

### Key Features

- ✅ Modular cog architecture for easy feature addition
- ✅ Comprehensive error handling with telemetry
- ✅ Database connection pooling and optimization
- ✅ Both prefix and slash command support
- ✅ Async/await throughout for performance
- ✅ Property-based testing with Hypothesis
- ✅ Type hints for better code quality
- ✅ Structured logging for debugging

## Getting Help

### Documentation Search

Use the [Index](INDEX.md) to search all documentation by topic.

### Common Questions

- **How do I set up the bot locally?** → [Developer Setup](developer/getting-started.md)
- **What commands are available?** → [Commands](user/commands/)
- **How do I create a new feature?** → [Creating Cogs](developer/guides/creating-cogs.md)
- **How do I deploy to production?** → [Production Deployment](operations/deployment/production.md)
- **Where are the tests?** → [Testing Guide](developer/guides/testing.md)

### Support Channels

- **GitHub Issues**: Report bugs or request features
- **Documentation**: Check this documentation first
- **Code Comments**: Inline documentation in the codebase

## Documentation Structure

```
docs/
├── README.md (this file)      # Documentation hub
├── INDEX.md                    # Complete documentation index
│
├── user/                       # User-facing documentation
│   ├── getting-started.md      # User quick start
│   ├── commands/               # Command reference
│   ├── features.md             # Feature descriptions
│   └── troubleshooting.md      # User troubleshooting
│
├── developer/                  # Developer documentation
│   ├── getting-started.md      # Dev setup
│   ├── setup/                  # Setup guides
│   ├── architecture/           # Architecture docs
│   ├── guides/                 # How-to guides
│   ├── reference/              # API reference
│   └── advanced/               # Advanced topics
│
├── operations/                 # Operations documentation
│   ├── deployment/             # Deployment guides
│   ├── database/               # Database operations
│   ├── monitoring.md           # Monitoring
│   └── maintenance.md          # Maintenance
│
├── meta/                       # Meta documentation
│   ├── contributing.md         # Contribution guide
│   ├── documentation-guide.md  # Doc writing guide
│   ├── changelog.md            # Version history
│   └── archived/               # Archived docs
│
└── project/                    # Project management
    ├── roadmap.md              # Future plans
    └── completed/              # Completed plans
```

## Documentation Updates

This documentation was reorganized on 2025-10-27. If you find broken links or outdated information:

1. Check the [INDEX.md](INDEX.md) for the current location
2. File a GitHub issue
3. Submit a pull request with fixes

## Related Files

- **[CLAUDE.md](../CLAUDE.md)** - Quick reference for AI assistants
- **[README.md](../README.md)** - Project overview
- **[CONTRIBUTING.md](meta/contributing.md)** - Contribution guidelines

---

**Happy coding! 🎉**

Need help? Start with the [Getting Started Guide](developer/getting-started.md) or check the [Index](INDEX.md).
