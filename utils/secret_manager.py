"""
Secret management utilities for Twi Bot Shard.

This module provides utilities for securely managing secrets and credentials,
including encryption, validation, monitoring, and rotation policies.
"""

import base64
import json
import logging
import os
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union, Tuple, Set

import discord
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger("secret_manager")


class SecretManager:
    """
    Manager for securely handling secrets and credentials.

    This class provides methods for encrypting and decrypting sensitive values,
    validating secrets, monitoring for suspicious activity, and managing credential
    rotation policies.
    """

    def __init__(self, bot, encryption_key: Optional[str] = None):
        """
        Initialize the secret manager.

        Args:
            bot: The bot instance
            encryption_key: Optional encryption key for encrypting/decrypting secrets
        """
        self.bot = bot
        self.logger = logging.getLogger("secret_manager")

        # Initialize encryption
        self._encryption_key = encryption_key or os.getenv("SECRET_ENCRYPTION_KEY")
        if self._encryption_key:
            # Derive a key from the encryption key
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b"twi_bot_shard_salt",  # Fixed salt for deterministic key derivation
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(self._encryption_key.encode()))
            self._cipher = Fernet(key)
        else:
            self._cipher = None
            self.logger.warning(
                "No encryption key provided. Secrets will not be encrypted."
            )

        # Initialize credential metadata
        self._credential_metadata = {}

    async def _init_db(self):
        """Initialize the database tables for secret management."""
        try:
            # Create credential_metadata table if it doesn't exist
            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS credential_metadata (
                    credential_name VARCHAR(255) PRIMARY KEY,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_rotated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    rotation_interval_days INT DEFAULT 90,
                    next_rotation_at TIMESTAMP,
                    metadata JSONB
                )
            """
            )

            # Create audit_log table if it doesn't exist
            await self.bot.db.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_id BIGINT,
                    action VARCHAR(255) NOT NULL,
                    resource_type VARCHAR(255),
                    resource_id VARCHAR(255),
                    details JSONB,
                    ip_address VARCHAR(45),
                    success BOOLEAN DEFAULT TRUE
                )
            """
            )

            self.logger.info("Secret management tables initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize secret management tables: {e}")
            raise

    async def setup(self):
        """Set up the secret manager."""
        await self._init_db()
        await self._load_credential_metadata()

    async def _load_credential_metadata(self):
        """Load credential metadata from the database."""
        try:
            records = await self.bot.db.fetch(
                """
                SELECT credential_name, created_at, last_rotated_at, 
                       rotation_interval_days, next_rotation_at, metadata
                FROM credential_metadata
            """
            )

            for record in records:
                self._credential_metadata[record["credential_name"]] = {
                    "created_at": record["created_at"],
                    "last_rotated_at": record["last_rotated_at"],
                    "rotation_interval_days": record["rotation_interval_days"],
                    "next_rotation_at": record["next_rotation_at"],
                    "metadata": (
                        json.loads(record["metadata"]) if record["metadata"] else {}
                    ),
                }

            self.logger.info(f"Loaded metadata for {len(records)} credentials")
        except Exception as e:
            self.logger.error(f"Failed to load credential metadata: {e}")

    def encrypt(self, value: str) -> str:
        """
        Encrypt a sensitive value.

        Args:
            value: The value to encrypt

        Returns:
            The encrypted value as a base64-encoded string

        Raises:
            ValueError: If encryption is not available
        """
        if not self._cipher:
            raise ValueError("Encryption is not available. No encryption key provided.")

        encrypted = self._cipher.encrypt(value.encode())
        return base64.urlsafe_b64encode(encrypted).decode()

    def decrypt(self, encrypted_value: str) -> str:
        """
        Decrypt an encrypted value.

        Args:
            encrypted_value: The encrypted value as a base64-encoded string

        Returns:
            The decrypted value

        Raises:
            ValueError: If encryption is not available
        """
        if not self._cipher:
            raise ValueError("Encryption is not available. No encryption key provided.")

        encrypted = base64.urlsafe_b64decode(encrypted_value.encode())
        return self._cipher.decrypt(encrypted).decode()

    async def register_credential(
        self,
        name: str,
        rotation_interval_days: int = 90,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Register a credential for tracking and rotation.

        Args:
            name: The name of the credential
            rotation_interval_days: The number of days between rotations
            metadata: Optional metadata about the credential
        """
        try:
            now = datetime.now()
            next_rotation = now + timedelta(days=rotation_interval_days)

            # Check if credential already exists
            existing = await self.bot.db.fetchval(
                """
                SELECT credential_name FROM credential_metadata
                WHERE credential_name = $1
            """,
                name,
            )

            if existing:
                # Update existing record
                await self.bot.db.execute(
                    """
                    UPDATE credential_metadata
                    SET rotation_interval_days = $2,
                        next_rotation_at = $3,
                        metadata = $4
                    WHERE credential_name = $1
                """,
                    name,
                    rotation_interval_days,
                    next_rotation,
                    json.dumps(metadata) if metadata else None,
                )
            else:
                # Insert new record
                await self.bot.db.execute(
                    """
                    INSERT INTO credential_metadata (
                        credential_name, rotation_interval_days, 
                        next_rotation_at, metadata
                    )
                    VALUES ($1, $2, $3, $4)
                """,
                    name,
                    rotation_interval_days,
                    next_rotation,
                    json.dumps(metadata) if metadata else None,
                )

            # Update in-memory cache
            self._credential_metadata[name] = {
                "created_at": now,
                "last_rotated_at": now,
                "rotation_interval_days": rotation_interval_days,
                "next_rotation_at": next_rotation,
                "metadata": metadata or {},
            }

            self.logger.info(f"Registered credential: {name}")

            # Log the action
            await self.log_audit_event(
                None,  # No user ID for system actions
                "register_credential",
                "credential",
                name,
                {"rotation_interval_days": rotation_interval_days},
            )
        except Exception as e:
            self.logger.error(f"Failed to register credential {name}: {e}")
            raise

    async def rotate_credential(
        self, name: str, new_value: Optional[str] = None, user_id: Optional[int] = None
    ) -> None:
        """
        Mark a credential as rotated.

        Args:
            name: The name of the credential
            new_value: Optional new value for the credential
            user_id: Optional ID of the user who rotated the credential
        """
        try:
            now = datetime.now()

            # Check if credential exists
            metadata = await self.bot.db.fetchrow(
                """
                SELECT rotation_interval_days, metadata
                FROM credential_metadata
                WHERE credential_name = $1
            """,
                name,
            )

            if not metadata:
                raise ValueError(f"Credential {name} not registered")

            rotation_interval_days = metadata["rotation_interval_days"]
            next_rotation = now + timedelta(days=rotation_interval_days)

            # Update the record
            await self.bot.db.execute(
                """
                UPDATE credential_metadata
                SET last_rotated_at = $2,
                    next_rotation_at = $3
                WHERE credential_name = $1
            """,
                name,
                now,
                next_rotation,
            )

            # Update in-memory cache
            if name in self._credential_metadata:
                self._credential_metadata[name]["last_rotated_at"] = now
                self._credential_metadata[name]["next_rotation_at"] = next_rotation

            self.logger.info(f"Rotated credential: {name}")

            # Log the action
            await self.log_audit_event(
                user_id,
                "rotate_credential",
                "credential",
                name,
                {"rotated_at": now.isoformat()},
            )
        except Exception as e:
            self.logger.error(f"Failed to rotate credential {name}: {e}")
            raise

    async def get_credentials_due_for_rotation(self) -> List[Dict[str, Any]]:
        """
        Get a list of credentials that are due for rotation.

        Returns:
            A list of credential metadata dictionaries
        """
        try:
            now = datetime.now()

            records = await self.bot.db.fetch(
                """
                SELECT credential_name, created_at, last_rotated_at, 
                       rotation_interval_days, next_rotation_at, metadata
                FROM credential_metadata
                WHERE next_rotation_at <= $1
            """,
                now,
            )

            result = []
            for record in records:
                result.append(
                    {
                        "name": record["credential_name"],
                        "created_at": record["created_at"],
                        "last_rotated_at": record["last_rotated_at"],
                        "rotation_interval_days": record["rotation_interval_days"],
                        "next_rotation_at": record["next_rotation_at"],
                        "metadata": (
                            json.loads(record["metadata"]) if record["metadata"] else {}
                        ),
                    }
                )

            return result
        except Exception as e:
            self.logger.error(f"Failed to get credentials due for rotation: {e}")
            return []

    async def log_audit_event(
        self,
        user_id: Optional[int],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        success: bool = True,
    ) -> None:
        """
        Log an audit event.

        Args:
            user_id: The ID of the user who performed the action
            action: The action that was performed
            resource_type: The type of resource that was affected
            resource_id: The ID of the resource that was affected
            details: Additional details about the action
            ip_address: The IP address of the user
            success: Whether the action was successful
        """
        try:
            await self.bot.db.execute(
                """
                INSERT INTO audit_log (
                    user_id, action, resource_type, resource_id,
                    details, ip_address, success
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7)
            """,
                user_id,
                action,
                resource_type,
                resource_id,
                json.dumps(details) if details else None,
                ip_address,
                success,
            )

            self.logger.debug(
                f"Logged audit event: {action} on {resource_type}/{resource_id} by user {user_id}"
            )
        except Exception as e:
            self.logger.error(f"Failed to log audit event: {e}")

    async def get_audit_logs(
        self,
        user_id: Optional[int] = None,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Get audit logs matching the specified criteria.

        Args:
            user_id: Filter by user ID
            action: Filter by action
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_time: Filter by start time
            end_time: Filter by end time
            limit: Maximum number of logs to return
            offset: Offset for pagination

        Returns:
            A list of audit log dictionaries
        """
        try:
            # Build the query
            query = """
                SELECT id, timestamp, user_id, action, resource_type,
                       resource_id, details, ip_address, success
                FROM audit_log
                WHERE 1=1
            """
            params = []
            param_index = 1

            if user_id is not None:
                query += f" AND user_id = ${param_index}"
                params.append(user_id)
                param_index += 1

            if action:
                query += f" AND action = ${param_index}"
                params.append(action)
                param_index += 1

            if resource_type:
                query += f" AND resource_type = ${param_index}"
                params.append(resource_type)
                param_index += 1

            if resource_id:
                query += f" AND resource_id = ${param_index}"
                params.append(resource_id)
                param_index += 1

            if start_time:
                query += f" AND timestamp >= ${param_index}"
                params.append(start_time)
                param_index += 1

            if end_time:
                query += f" AND timestamp <= ${param_index}"
                params.append(end_time)
                param_index += 1

            query += " ORDER BY timestamp DESC"
            query += f" LIMIT ${param_index}"
            params.append(limit)
            param_index += 1

            query += f" OFFSET ${param_index}"
            params.append(offset)

            # Execute the query
            records = await self.bot.db.fetch(query, *params)

            # Convert to dictionaries
            result = []
            for record in records:
                result.append(
                    {
                        "id": record["id"],
                        "timestamp": record["timestamp"],
                        "user_id": record["user_id"],
                        "action": record["action"],
                        "resource_type": record["resource_type"],
                        "resource_id": record["resource_id"],
                        "details": (
                            json.loads(record["details"]) if record["details"] else None
                        ),
                        "ip_address": record["ip_address"],
                        "success": record["success"],
                    }
                )

            return result
        except Exception as e:
            self.logger.error(f"Failed to get audit logs: {e}")
            return []

    def validate_secret(self, secret: str) -> Tuple[bool, List[str]]:
        """
        Validate a secret against security requirements.

        Args:
            secret: The secret to validate

        Returns:
            A tuple containing (is_valid, list_of_issues)
        """
        issues = []

        # Check length
        if len(secret) < 12:
            issues.append("Secret should be at least 12 characters long")

        # Check complexity
        if not re.search(r"[A-Z]", secret):
            issues.append("Secret should contain at least one uppercase letter")
        if not re.search(r"[a-z]", secret):
            issues.append("Secret should contain at least one lowercase letter")
        if not re.search(r"[0-9]", secret):
            issues.append("Secret should contain at least one digit")
        if not re.search(r"[^A-Za-z0-9]", secret):
            issues.append("Secret should contain at least one special character")

        # Check for common patterns
        common_patterns = [
            r"password",
            r"123456",
            r"qwerty",
            r"admin",
            r"welcome",
            r"letmein",
            r"monkey",
            r"abc123",
            r"football",
            r"iloveyou",
        ]
        for pattern in common_patterns:
            if re.search(pattern, secret.lower()):
                issues.append(f"Secret contains a common pattern: {pattern}")
                break

        return (len(issues) == 0, issues)

    async def schedule_credential_rotation(
        self,
        name: str,
        notification_days: List[int] = [30, 14, 7, 3, 1],
        notification_channel_id: Optional[int] = None,
    ) -> None:
        """
        Schedule notifications for credential rotation.

        Args:
            name: The name of the credential
            notification_days: List of days before expiration to send notifications
            notification_channel_id: Discord channel ID to send notifications to
        """
        try:
            # Check if credential exists
            metadata = await self.bot.db.fetchrow(
                """
                SELECT next_rotation_at, metadata
                FROM credential_metadata
                WHERE credential_name = $1
            """,
                name,
            )

            if not metadata:
                raise ValueError(f"Credential {name} not registered")

            next_rotation = metadata["next_rotation_at"]
            current_metadata = (
                json.loads(metadata["metadata"]) if metadata["metadata"] else {}
            )

            # Update metadata with notification settings
            current_metadata.update(
                {
                    "notification_days": notification_days,
                    "notification_channel_id": notification_channel_id,
                    "last_notification_sent": None,
                }
            )

            # Update the record
            await self.bot.db.execute(
                """
                UPDATE credential_metadata
                SET metadata = $2
                WHERE credential_name = $1
            """,
                name,
                json.dumps(current_metadata),
            )

            # Update in-memory cache
            if name in self._credential_metadata:
                self._credential_metadata[name]["metadata"].update(
                    {
                        "notification_days": notification_days,
                        "notification_channel_id": notification_channel_id,
                        "last_notification_sent": None,
                    }
                )

            self.logger.info(f"Scheduled rotation notifications for credential: {name}")

            # Log the action
            await self.log_audit_event(
                None,  # No user ID for system actions
                "schedule_credential_rotation",
                "credential",
                name,
                {
                    "notification_days": notification_days,
                    "notification_channel_id": notification_channel_id,
                },
            )
        except Exception as e:
            self.logger.error(f"Failed to schedule credential rotation for {name}: {e}")
            raise

    async def check_pending_notifications(self) -> None:
        """
        Check for pending credential rotation notifications and send them.

        This method should be called periodically, e.g., once a day.
        """
        try:
            now = datetime.now()

            # Get all credentials
            records = await self.bot.db.fetch(
                """
                SELECT credential_name, next_rotation_at, metadata
                FROM credential_metadata
            """
            )

            for record in records:
                name = record["credential_name"]
                next_rotation = record["next_rotation_at"]
                metadata = json.loads(record["metadata"]) if record["metadata"] else {}

                # Skip if no notification settings
                if "notification_days" not in metadata:
                    continue

                notification_days = metadata.get("notification_days", [])
                notification_channel_id = metadata.get("notification_channel_id")
                last_notification_sent = metadata.get("last_notification_sent")

                # Calculate days until rotation
                days_until_rotation = (next_rotation - now).days

                # Check if we need to send a notification
                if days_until_rotation in notification_days:
                    # Check if we've already sent this notification
                    if last_notification_sent:
                        last_sent_days = int(last_notification_sent)
                        if last_sent_days <= days_until_rotation:
                            # Already sent a notification for this or a closer deadline
                            continue

                    # Send notification
                    await self.notify_credential_rotation(
                        name, days_until_rotation, notification_channel_id
                    )

                    # Update last notification sent
                    metadata["last_notification_sent"] = days_until_rotation
                    await self.bot.db.execute(
                        """
                        UPDATE credential_metadata
                        SET metadata = $2
                        WHERE credential_name = $1
                    """,
                        name,
                        json.dumps(metadata),
                    )

                    # Update in-memory cache
                    if name in self._credential_metadata:
                        self._credential_metadata[name]["metadata"][
                            "last_notification_sent"
                        ] = days_until_rotation
        except Exception as e:
            self.logger.error(f"Failed to check pending notifications: {e}")

    async def notify_credential_rotation(
        self, name: str, days_until_rotation: int, channel_id: Optional[int] = None
    ) -> None:
        """
        Send a notification about an upcoming credential rotation.

        Args:
            name: The name of the credential
            days_until_rotation: Number of days until rotation is due
            channel_id: Discord channel ID to send the notification to
        """
        try:
            # Get credential metadata
            metadata = await self.bot.db.fetchrow(
                """
                SELECT metadata
                FROM credential_metadata
                WHERE credential_name = $1
            """,
                name,
            )

            if not metadata:
                raise ValueError(f"Credential {name} not registered")

            credential_metadata = (
                json.loads(metadata["metadata"]) if metadata["metadata"] else {}
            )
            description = credential_metadata.get("description", name)
            env_vars = credential_metadata.get("environment_variables", [])
            rotation_instructions = credential_metadata.get("rotation_instructions", "")

            # Create notification message
            if days_until_rotation <= 0:
                title = f"⚠️ URGENT: {description} Rotation Overdue"
                color = discord.Color.red()
            elif days_until_rotation == 1:
                title = f"⚠️ URGENT: {description} Rotation Due Tomorrow"
                color = discord.Color.orange()
            elif days_until_rotation <= 7:
                title = f"⚠️ {description} Rotation Due in {days_until_rotation} Days"
                color = discord.Color.gold()
            else:
                title = f"📅 {description} Rotation Due in {days_until_rotation} Days"
                color = discord.Color.blue()

            embed = discord.Embed(
                title=title,
                description=f"The following credential needs to be rotated:\n**{name}**",
                color=color,
                timestamp=datetime.now(),
            )

            if env_vars:
                embed.add_field(
                    name="Environment Variables",
                    value="\n".join([f"`{var}`" for var in env_vars]),
                    inline=False,
                )

            if rotation_instructions:
                embed.add_field(
                    name="Rotation Instructions",
                    value=rotation_instructions,
                    inline=False,
                )

            embed.set_footer(text=f"Credential ID: {name}")

            # Send notification
            if channel_id:
                try:
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        await channel.send(embed=embed)
                        self.logger.info(
                            f"Sent rotation notification for {name} to channel {channel_id}"
                        )
                    else:
                        self.logger.warning(
                            f"Could not find channel {channel_id} for credential rotation notification"
                        )
                except Exception as e:
                    self.logger.error(
                        f"Failed to send notification to channel {channel_id}: {e}"
                    )

            # Log the notification
            await self.log_audit_event(
                None,  # No user ID for system actions
                "credential_rotation_notification",
                "credential",
                name,
                {"days_until_rotation": days_until_rotation},
            )
        except Exception as e:
            self.logger.error(f"Failed to notify credential rotation for {name}: {e}")

    async def check_credential_health(self, name: str) -> Dict[str, Any]:
        """
        Check the health and security of a credential.

        Args:
            name: The name of the credential

        Returns:
            A dictionary with health check results
        """
        try:
            # Get credential metadata
            metadata = await self.bot.db.fetchrow(
                """
                SELECT created_at, last_rotated_at, rotation_interval_days, next_rotation_at, metadata
                FROM credential_metadata
                WHERE credential_name = $1
            """,
                name,
            )

            if not metadata:
                raise ValueError(f"Credential {name} not registered")

            now = datetime.now()
            created_at = metadata["created_at"]
            last_rotated_at = metadata["last_rotated_at"]
            rotation_interval_days = metadata["rotation_interval_days"]
            next_rotation_at = metadata["next_rotation_at"]
            credential_metadata = (
                json.loads(metadata["metadata"]) if metadata["metadata"] else {}
            )

            # Calculate health metrics
            days_since_rotation = (now - last_rotated_at).days
            days_until_rotation = (next_rotation_at - now).days
            rotation_percentage = min(
                100, max(0, (days_since_rotation / rotation_interval_days) * 100)
            )

            # Determine health status
            if days_until_rotation < 0:
                health_status = "critical"
                health_message = f"Rotation overdue by {abs(days_until_rotation)} days"
            elif days_until_rotation <= 7:
                health_status = "warning"
                health_message = f"Rotation due in {days_until_rotation} days"
            else:
                health_status = "healthy"
                health_message = f"Rotation due in {days_until_rotation} days"

            # Check if credential is too old
            max_age_days = 365  # 1 year
            days_since_creation = (now - created_at).days
            if days_since_creation > max_age_days:
                age_status = "warning"
                age_message = f"Credential is {days_since_creation} days old (recommended max: {max_age_days} days)"
            else:
                age_status = "healthy"
                age_message = f"Credential age is within recommended limits"

            # Compile results
            result = {
                "name": name,
                "created_at": created_at,
                "last_rotated_at": last_rotated_at,
                "days_since_rotation": days_since_rotation,
                "days_until_rotation": days_until_rotation,
                "rotation_percentage": rotation_percentage,
                "health_status": health_status,
                "health_message": health_message,
                "age_status": age_status,
                "age_message": age_message,
                "metadata": credential_metadata,
            }

            # Log the health check
            await self.log_audit_event(
                None,  # No user ID for system actions
                "credential_health_check",
                "credential",
                name,
                {
                    "health_status": health_status,
                    "days_until_rotation": days_until_rotation,
                },
            )

            return result
        except Exception as e:
            self.logger.error(f"Failed to check credential health for {name}: {e}")
            raise

    async def export_audit_logs(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: str = "json",
    ) -> str:
        """
        Export audit logs for compliance purposes.

        Args:
            start_time: Start time for log export
            end_time: End time for log export
            format: Export format ('json' or 'csv')

        Returns:
            The exported logs as a string
        """
        try:
            # Default to last 30 days if no time range specified
            if not start_time:
                start_time = datetime.now() - timedelta(days=30)
            if not end_time:
                end_time = datetime.now()

            # Get logs
            logs = await self.get_audit_logs(
                start_time=start_time,
                end_time=end_time,
                limit=10000,  # Set a high limit for export
            )

            if format.lower() == "csv":
                # Generate CSV
                csv_lines = [
                    "id,timestamp,user_id,action,resource_type,resource_id,details,ip_address,success"
                ]

                for log in logs:
                    details_str = (
                        json.dumps(log["details"]).replace('"', '""')
                        if log["details"]
                        else ""
                    )
                    csv_lines.append(
                        f"{log['id']},{log['timestamp'].isoformat()},{log['user_id'] or ''},"
                        f"{log['action']},{log['resource_type'] or ''},{log['resource_id'] or ''},"
                        f"\"{details_str}\",{log['ip_address'] or ''},{log['success']}"
                    )

                return "\n".join(csv_lines)
            else:
                # Default to JSON
                return json.dumps(logs, default=str, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to export audit logs: {e}")
            raise

    async def detect_suspicious_activity(
        self,
        lookback_hours: int = 24,
        threshold_actions: int = 20,
        threshold_failures: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Detect suspicious activity patterns in audit logs.

        Args:
            lookback_hours: Hours to look back for suspicious activity
            threshold_actions: Threshold for number of actions to be considered suspicious
            threshold_failures: Threshold for number of failures to be considered suspicious

        Returns:
            A list of suspicious activity reports
        """
        try:
            start_time = datetime.now() - timedelta(hours=lookback_hours)

            # Get all logs in the time period
            logs = await self.get_audit_logs(
                start_time=start_time, limit=10000  # Set a high limit
            )

            # Group by user_id and IP address
            user_actions = {}
            ip_actions = {}

            for log in logs:
                user_id = log["user_id"]
                ip_address = log["ip_address"]
                success = log["success"]

                # Track by user_id
                if user_id:
                    if user_id not in user_actions:
                        user_actions[user_id] = {
                            "total": 0,
                            "failures": 0,
                            "actions": set(),
                        }

                    user_actions[user_id]["total"] += 1
                    user_actions[user_id]["actions"].add(log["action"])
                    if not success:
                        user_actions[user_id]["failures"] += 1

                # Track by IP address
                if ip_address:
                    if ip_address not in ip_actions:
                        ip_actions[ip_address] = {
                            "total": 0,
                            "failures": 0,
                            "user_ids": set(),
                        }

                    ip_actions[ip_address]["total"] += 1
                    if user_id:
                        ip_actions[ip_address]["user_ids"].add(user_id)
                    if not success:
                        ip_actions[ip_address]["failures"] += 1

            # Identify suspicious patterns
            suspicious_activity = []

            # Check for users with many actions or failures
            for user_id, stats in user_actions.items():
                if (
                    stats["total"] >= threshold_actions
                    or stats["failures"] >= threshold_failures
                ):
                    suspicious_activity.append(
                        {
                            "type": "user_activity",
                            "user_id": user_id,
                            "total_actions": stats["total"],
                            "failed_actions": stats["failures"],
                            "unique_actions": len(stats["actions"]),
                            "actions": list(stats["actions"]),
                            "severity": (
                                "high"
                                if stats["failures"] >= threshold_failures
                                else "medium"
                            ),
                        }
                    )

            # Check for IPs with many actions, failures, or multiple users
            for ip_address, stats in ip_actions.items():
                if (
                    stats["total"] >= threshold_actions
                    or stats["failures"] >= threshold_failures
                    or len(stats["user_ids"]) > 1
                ):
                    suspicious_activity.append(
                        {
                            "type": "ip_activity",
                            "ip_address": ip_address,
                            "total_actions": stats["total"],
                            "failed_actions": stats["failures"],
                            "unique_users": len(stats["user_ids"]),
                            "user_ids": list(stats["user_ids"]),
                            "severity": (
                                "high"
                                if stats["failures"] >= threshold_failures
                                else "medium"
                            ),
                        }
                    )

            # Log if suspicious activity found
            if suspicious_activity:
                self.logger.warning(
                    f"Detected {len(suspicious_activity)} instances of suspicious activity"
                )

                # Log the detection
                await self.log_audit_event(
                    None,  # No user ID for system actions
                    "suspicious_activity_detection",
                    "audit_log",
                    None,
                    {
                        "suspicious_count": len(suspicious_activity),
                        "lookback_hours": lookback_hours,
                    },
                )

            return suspicious_activity
        except Exception as e:
            self.logger.error(f"Failed to detect suspicious activity: {e}")
            return []


# Global secret manager instance
_secret_manager = None


def get_secret_manager():
    """Get the global secret manager instance."""
    if _secret_manager is None:
        raise RuntimeError(
            "Secret manager not initialized. Call init_secret_manager first."
        )
    return _secret_manager


def init_secret_manager(bot, encryption_key=None):
    """Initialize the global secret manager instance."""
    global _secret_manager
    _secret_manager = SecretManager(bot, encryption_key)
    return _secret_manager


async def setup_secret_manager(bot, encryption_key=None):
    """
    Set up the secret manager.

    This function initializes the secret manager and creates the necessary database tables.
    It should be called during bot startup.

    Args:
        bot: The bot instance
        encryption_key: Optional encryption key for encrypting/decrypting secrets
    """
    manager = init_secret_manager(bot, encryption_key)
    await manager.setup()

    # Register default credentials
    await register_default_credentials(manager)

    return manager


async def register_default_credentials(manager):
    """
    Register default credentials for tracking and rotation.

    Args:
        manager: The secret manager instance
    """
    # Register database credentials
    await manager.register_credential(
        "database",
        rotation_interval_days=90,
        metadata={
            "description": "Database credentials",
            "environment_variables": ["DB_USER", "DB_PASSWORD"],
            "rotation_instructions": "Update the database user password and update the .env file",
        },
    )

    # Register Discord bot token
    await manager.register_credential(
        "discord_bot_token",
        rotation_interval_days=180,
        metadata={
            "description": "Discord bot token",
            "environment_variables": ["BOT_TOKEN"],
            "rotation_instructions": "Generate a new bot token in the Discord Developer Portal and update the .env file",
        },
    )

    # Register other API credentials
    for credential in [
        ("google_api", 90, ["GOOGLE_API_KEY", "GOOGLE_CSE_ID"]),
        (
            "twitter_api",
            90,
            ["TWITTER_API_KEY", "TWITTER_API_KEY_SECRET", "TWITTER_BEARER_TOKEN"],
        ),
        ("openai_api", 90, ["OPENAI_API_KEY"]),
    ]:
        name, interval, env_vars = credential
        await manager.register_credential(
            name,
            rotation_interval_days=interval,
            metadata={
                "description": f'{name.replace("_", " ").title()} credentials',
                "environment_variables": env_vars,
                "rotation_instructions": f'Generate new {name.replace("_", " ")} credentials and update the .env file',
            },
        )
