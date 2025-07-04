# Twi Bot Shard Deployment Guide

This guide provides comprehensive instructions for deploying the Twi Bot Shard in various environments, from local development to production.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Local Deployment](#local-deployment)
3. [Docker Deployment](#docker-deployment)
4. [Infrastructure as Code Deployment](#infrastructure-as-code-deployment)
5. [Continuous Deployment](#continuous-deployment)
6. [Post-Deployment Verification](#post-deployment-verification)
7. [Troubleshooting](#troubleshooting)

## Prerequisites

Before deploying Twi Bot Shard, ensure you have the following:

### System Requirements

- **Python**: Version 3.12 or higher
- **PostgreSQL**: Version 13 or higher
- **Discord Bot Token**: Created through the [Discord Developer Portal](https://discord.com/developers/applications)
- **SSL Certificates**: For secure database connections

### Required Accounts

- **Discord Developer Account**: For creating and managing the bot
- **Google Cloud Account** (optional): If using Google services for search functionality
- **OpenAI Account** (optional): If using AI features

### Development Tools

- **Git**: For version control
- **Docker** and **Docker Compose**: For containerized deployment
- **Terraform** (optional): For infrastructure as code deployment

## Local Deployment

### 1. Clone the Repository

```bash
git clone https://github.com/username/twi_bot_shard.git
cd twi_bot_shard
```

### 2. Set Up Virtual Environment

```bash
# Using uv (recommended)
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
uv pip install -e .
```

### 3. Configure Environment Variables

Create a `.env` file in the project root with the required variables:

```
BOT_TOKEN=your_discord_bot_token
GOOGLE_API_KEY=your_google_api_key
GOOGLE_CSE_ID=your_google_cse_id
HOST=your_database_host
DB_USER=your_database_user
DB_PASSWORD=your_database_password
DATABASE=your_database_name
PORT=5432
KILL_AFTER=0
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
USER_AGENT=your_user_agent
USERNAME=your_username
PASSWORD=your_password
LOGFILE=test
WEBHOOK_TESTING_LOG=your_webhook_testing_log
WEBHOOK=your_webhook
TWITTER_API_KEY=your_twitter_api_key
TWITTER_API_KEY_SECRET=your_twitter_api_key_secret
TWITTER_BEARER_TOKEN=your_twitter_bearer_token
TWITTER_ACCESS_TOKEN=your_twitter_access_token
TWITTER_ACCESS_TOKEN_SECRET=your_twitter_access_token_secret
AO3_USERNAME=your_ao3_username
AO3_PASSWORD=your_ao3_password
OPENAI_API_KEY=your_openai_api_key
```

### 4. Set Up the Database

1. Create a PostgreSQL database:

```bash
createdb twi_bot_shard
```

2. Apply the database schema:

```bash
psql -d twi_bot_shard -f database/cognita_db_tables.sql
```

3. Apply database optimizations:

```bash
psql -d twi_bot_shard -f database/db_optimizations.sql
```

### 5. Run the Bot

```bash
python main.py
```

## Docker Deployment

### 1. Build the Docker Image

```bash
docker build -t twi-bot-shard:latest .
```

### 2. Run with Docker Compose

Create a `docker-compose.yml` file:

```yaml
version: '3.8'

services:
  bot:
    image: twi-bot-shard:latest
    restart: unless-stopped
    env_file: .env
    volumes:
      - ./logs:/app/logs
      - ./ssl-cert:/app/ssl-cert
    depends_on:
      - db

  db:
    image: postgres:13-alpine
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: ${DATABASE}
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./database/cognita_db_tables.sql:/docker-entrypoint-initdb.d/01-schema.sql
      - ./database/db_optimizations.sql:/docker-entrypoint-initdb.d/02-optimizations.sql

volumes:
  postgres_data:
```

Start the services:

```bash
docker-compose up -d
```

### 3. Check Logs

```bash
docker-compose logs -f bot
```

## Infrastructure as Code Deployment

### Using Terraform with AWS

1. Create a `main.tf` file:

```hcl
provider "aws" {
  region = "us-west-2"
}

resource "aws_ecr_repository" "twi_bot_shard" {
  name = "twi-bot-shard"
}

resource "aws_ecs_cluster" "twi_bot_cluster" {
  name = "twi-bot-cluster"
}

resource "aws_ecs_task_definition" "twi_bot_task" {
  family                   = "twi-bot-task"
  container_definitions    = jsonencode([
    {
      name      = "twi-bot-shard"
      image     = "${aws_ecr_repository.twi_bot_shard.repository_url}:latest"
      essential = true
      secrets   = [
        {
          name      = "BOT_TOKEN"
          valueFrom = "arn:aws:ssm:us-west-2:123456789012:parameter/twi-bot/BOT_TOKEN"
        },
        # Add other environment variables as secrets
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/twi-bot-shard"
          "awslogs-region"        = "us-west-2"
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "256"
  memory                   = "512"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn
}

resource "aws_ecs_service" "twi_bot_service" {
  name            = "twi-bot-service"
  cluster         = aws_ecs_cluster.twi_bot_cluster.id
  task_definition = aws_ecs_task_definition.twi_bot_task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = ["subnet-12345678"]
    security_groups  = ["sg-12345678"]
    assign_public_ip = true
  }
}

# Define IAM roles, RDS database, etc.
```

2. Initialize and apply Terraform:

```bash
terraform init
terraform apply
```

## Continuous Deployment

### GitHub Actions Setup

Create a `.github/workflows/deploy.yml` file:

```yaml
name: Deploy

on:
  push:
    branches: [ main ]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v1
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: us-west-2
      
      - name: Login to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v1
      
      - name: Build, tag, and push image to Amazon ECR
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          ECR_REPOSITORY: twi-bot-shard
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
      
      - name: Update ECS service
        run: |
          aws ecs update-service --cluster twi-bot-cluster --service twi-bot-service --force-new-deployment
```

## Post-Deployment Verification

After deploying the bot, verify that it's working correctly:

1. **Check Bot Status**: Ensure the bot is online in Discord
2. **Run Basic Commands**: Test basic commands like `/help` and `/ping`
3. **Check Database Connection**: Verify that the bot can connect to the database
4. **Monitor Logs**: Check for any errors in the logs

### Verification Script

You can use this script to verify the deployment:

```bash
#!/bin/bash

# Check if the bot is running
if docker ps | grep -q twi-bot-shard; then
  echo "✅ Bot container is running"
else
  echo "❌ Bot container is not running"
  exit 1
fi

# Check logs for errors
if docker logs --tail 100 twi-bot-shard 2>&1 | grep -i error; then
  echo "⚠️ Errors found in logs"
else
  echo "✅ No errors found in logs"
fi

# Check database connection
if docker exec twi-bot-shard python -c "from utils.db import check_connection; import asyncio; print(asyncio.run(check_connection()))"; then
  echo "✅ Database connection successful"
else
  echo "❌ Database connection failed"
  exit 1
fi

echo "Deployment verification completed"
```

## Troubleshooting

### Common Issues

#### Bot Doesn't Connect to Discord

1. Check if the `BOT_TOKEN` is correct
2. Ensure the bot has the necessary intents enabled in the Discord Developer Portal
3. Check network connectivity to Discord's API

#### Database Connection Issues

1. Verify database credentials in the `.env` file
2. Check if the database server is running and accessible
3. Ensure SSL certificates are properly configured

#### Container Fails to Start

1. Check Docker logs: `docker logs twi-bot-shard`
2. Verify that all required environment variables are set
3. Ensure the container has enough resources (CPU/memory)

### Getting Help

If you encounter issues not covered in this guide:

1. Check the project's GitHub repository for known issues
2. Join the support Discord server
3. Contact the development team

---

This deployment guide will be updated as the deployment process evolves. For the latest information, refer to the project's documentation repository.