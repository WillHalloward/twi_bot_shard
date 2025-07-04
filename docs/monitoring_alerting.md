# Twi Bot Shard Monitoring and Alerting Guide

This guide provides comprehensive information on monitoring the Twi Bot Shard application, setting up alerts, and responding to incidents.

## Table of Contents

1. [Monitoring Strategy](#monitoring-strategy)
2. [Key Metrics](#key-metrics)
3. [Logging Configuration](#logging-configuration)
4. [Monitoring Tools](#monitoring-tools)
5. [Alert Configuration](#alert-configuration)
6. [Incident Response](#incident-response)
7. [Dashboard Setup](#dashboard-setup)

## Monitoring Strategy

Effective monitoring of Twi Bot Shard requires a multi-layered approach that covers:

1. **Application Health**: Monitoring the bot's core functionality and responsiveness
2. **Resource Utilization**: Tracking CPU, memory, and network usage
3. **Database Performance**: Monitoring query performance and connection pool status
4. **External Dependencies**: Tracking API calls to Discord and other services
5. **Error Rates**: Monitoring application errors and exceptions

The monitoring strategy follows these principles:

- **Proactive Detection**: Identify issues before they affect users
- **Comprehensive Coverage**: Monitor all critical components
- **Actionable Alerts**: Ensure alerts provide clear information for troubleshooting
- **Minimal Noise**: Avoid alert fatigue by tuning thresholds appropriately

## Key Metrics

### Application Metrics

| Metric | Description | Warning Threshold | Critical Threshold |
|--------|-------------|-------------------|-------------------|
| Bot Uptime | Time since last restart | N/A | < 10 minutes |
| Command Latency | Time to process commands | > 1 second | > 3 seconds |
| Command Success Rate | Percentage of successful commands | < 95% | < 90% |
| Discord API Rate Limit | Percentage of rate limit remaining | < 30% | < 10% |
| Active Connections | Number of active Discord connections | N/A | < 1 |
| Event Processing Rate | Events processed per second | > 100 | > 200 |

### System Metrics

| Metric | Description | Warning Threshold | Critical Threshold |
|--------|-------------|-------------------|-------------------|
| CPU Usage | Percentage of CPU utilized | > 70% | > 90% |
| Memory Usage | Percentage of memory utilized | > 80% | > 95% |
| Disk Space | Free disk space | < 20% | < 10% |
| Network I/O | Network traffic in/out | > 80% capacity | > 95% capacity |

### Database Metrics

| Metric | Description | Warning Threshold | Critical Threshold |
|--------|-------------|-------------------|-------------------|
| Query Latency | Average time for query execution | > 100ms | > 500ms |
| Connection Pool Usage | Percentage of DB connections used | > 70% | > 90% |
| Database Size | Total size of the database | > 80% capacity | > 95% capacity |
| Index Hit Ratio | Percentage of index hits vs. scans | < 90% | < 80% |
| Transaction Rate | Transactions per second | > 100 | > 200 |

## Logging Configuration

Twi Bot Shard uses structured logging with contextual information to facilitate troubleshooting and analysis.

### Log Levels

- **DEBUG**: Detailed information, typically useful only for diagnosing problems
- **INFO**: Confirmation that things are working as expected
- **WARNING**: Indication that something unexpected happened, but the application is still working
- **ERROR**: Due to a more serious problem, the application has not been able to perform a function
- **CRITICAL**: A serious error indicating that the program itself may be unable to continue running

### Log Format

Logs are output in JSON format with the following fields:

```json
{
  "timestamp": "2023-06-15T12:34:56.789Z",
  "level": "INFO",
  "logger": "cog_name",
  "message": "Command executed successfully",
  "request_id": "abc123",
  "user_id": "123456789012345678",
  "guild_id": "876543210987654321",
  "command": "help",
  "execution_time_ms": 45,
  "additional_context": {}
}
```

### Log Storage

Logs are stored in multiple locations:

1. **Local Files**: Rotated daily, kept for 30 days
2. **Cloud Storage**: Archived for long-term storage (90 days)
3. **Log Management System**: Ingested for real-time analysis and alerting

## Monitoring Tools

### Prometheus

Prometheus is used for metrics collection and storage. The bot exposes metrics at the `/metrics` endpoint.

#### Installation

1. Add the Prometheus client to the bot:

```python
from prometheus_client import start_http_server, Counter, Gauge, Histogram

# Start metrics server
start_http_server(8000)

# Define metrics
COMMAND_COUNTER = Counter('bot_commands_total', 'Total commands processed', ['command', 'success'])
COMMAND_LATENCY = Histogram('bot_command_latency_seconds', 'Command processing time', ['command'])
ACTIVE_USERS = Gauge('bot_active_users', 'Number of active users')
```

2. Install Prometheus server:

```bash
docker run -d --name prometheus -p 9090:9090 -v /path/to/prometheus.yml:/etc/prometheus/prometheus.yml prom/prometheus
```

3. Configure `prometheus.yml`:

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'twi_bot_shard'
    static_configs:
      - targets: ['bot:8000']
```

### Grafana

Grafana is used for visualization and dashboarding.

#### Installation

```bash
docker run -d --name grafana -p 3000:3000 grafana/grafana
```

#### Dashboard Templates

Pre-configured dashboard templates are available in the `monitoring/dashboards` directory:

- `bot_overview.json`: General bot health and performance
- `system_metrics.json`: System resource utilization
- `database_performance.json`: Database metrics and query performance

### ELK Stack (Elasticsearch, Logstash, Kibana)

The ELK stack is used for log aggregation, analysis, and visualization.

#### Installation

Use the provided Docker Compose file in `monitoring/elk`:

```bash
cd monitoring/elk
docker-compose up -d
```

#### Logstash Configuration

Configure Logstash to parse the JSON logs:

```
input {
  file {
    path => "/app/logs/*.log"
    codec => "json"
  }
}

filter {
  date {
    match => [ "timestamp", "ISO8601" ]
  }
}

output {
  elasticsearch {
    hosts => ["elasticsearch:9200"]
    index => "twi-bot-logs-%{+YYYY.MM.dd}"
  }
}
```

## Alert Configuration

### Prometheus Alertmanager

Alertmanager is used to handle alerts from Prometheus.

#### Installation

```bash
docker run -d --name alertmanager -p 9093:9093 -v /path/to/alertmanager.yml:/etc/alertmanager/alertmanager.yml prom/alertmanager
```

#### Alert Rules

Create alert rules in `prometheus.yml`:

```yaml
rule_files:
  - 'alert_rules.yml'

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['alertmanager:9093']
```

Example `alert_rules.yml`:

```yaml
groups:
- name: bot_alerts
  rules:
  - alert: HighCommandLatency
    expr: avg(bot_command_latency_seconds) > 1
    for: 5m
    labels:
      severity: warning
    annotations:
      summary: "High command latency"
      description: "Command latency is above 1 second for 5 minutes"

  - alert: BotDown
    expr: up{job="twi_bot_shard"} == 0
    for: 1m
    labels:
      severity: critical
    annotations:
      summary: "Bot is down"
      description: "The bot has been down for more than 1 minute"
```

### Discord Webhook Notifications

Configure Alertmanager to send notifications to a Discord channel:

```yaml
receivers:
- name: 'discord'
  webhook_configs:
  - url: 'https://discord.com/api/webhooks/your_webhook_url'
    send_resolved: true

route:
  group_by: ['alertname']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 4h
  receiver: 'discord'
```

## Incident Response

### Incident Severity Levels

| Level | Description | Response Time | Escalation |
|-------|-------------|---------------|------------|
| P1 | Critical service outage | Immediate | All team members |
| P2 | Major functionality impaired | < 30 minutes | On-call engineer + backup |
| P3 | Minor issue affecting some users | < 2 hours | On-call engineer |
| P4 | Non-urgent issue | Next business day | Regular channels |

### Incident Response Process

1. **Alert**: System detects an issue and sends an alert
2. **Acknowledge**: On-call engineer acknowledges the alert
3. **Investigate**: Determine the root cause using logs and metrics
4. **Mitigate**: Apply immediate fix to restore service
5. **Resolve**: Implement permanent solution
6. **Review**: Conduct post-mortem analysis

### Escalation Path

1. **Primary On-Call Engineer**: First responder for all alerts
2. **Secondary On-Call Engineer**: Backup if primary is unavailable
3. **Engineering Lead**: Escalation point for P1/P2 incidents
4. **Project Owner**: Final escalation for critical incidents

## Dashboard Setup

### Main Bot Dashboard

The main dashboard provides an overview of the bot's health and performance:

![Bot Dashboard](monitoring/images/bot_dashboard.png)

#### Panels

1. **Bot Status**: Current status and uptime
2. **Command Activity**: Commands per minute with success/failure breakdown
3. **Latency Metrics**: Command processing time and Discord API latency
4. **Error Rate**: Errors per minute with breakdown by type
5. **Resource Usage**: CPU, memory, and network utilization

### Database Performance Dashboard

This dashboard focuses on database performance metrics:

![Database Dashboard](monitoring/images/db_dashboard.png)

#### Panels

1. **Query Performance**: Average query time by type
2. **Connection Pool**: Connection pool utilization
3. **Transaction Rate**: Transactions per second
4. **Slow Queries**: List of recent slow queries
5. **Index Usage**: Index hit ratio and table scans

### Log Analysis Dashboard

This dashboard provides insights from log data:

![Log Dashboard](monitoring/images/log_dashboard.png)

#### Panels

1. **Error Distribution**: Breakdown of errors by type and source
2. **User Activity**: Active users and command usage patterns
3. **Geographic Distribution**: User activity by region
4. **Feature Usage**: Most and least used features
5. **Error Timeline**: Error frequency over time

---

This monitoring and alerting guide will be updated as the monitoring infrastructure evolves. For the latest information, refer to the project's documentation repository.