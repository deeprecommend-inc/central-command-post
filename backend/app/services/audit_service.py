from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import hashlib
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession

from ..models.database import AuditWORM
from ..core.config import settings


class WORMAuditLogger:
    """Write-Once-Read-Many audit logger"""

    def __init__(self, storage_path: str = None):
        self.storage_path = Path(storage_path or settings.AUDIT_STORAGE_PATH)
        self.storage_path.mkdir(parents=True, exist_ok=True)

    def _generate_hash(self, data: Dict[str, Any]) -> str:
        """Generate hash of audit data for integrity verification"""
        data_str = json.dumps(data, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()

    async def write_to_immutable_storage(self, audit_record: AuditWORM) -> str:
        """
        Write audit log to immutable storage (append-only file)
        Returns: file path
        """
        # Use date-based file naming
        date_str = audit_record.timestamp.strftime("%Y%m%d")
        file_path = self.storage_path / f"audit_{date_str}.log"

        # Prepare log entry
        log_entry = {
            "id": audit_record.id,
            "timestamp": audit_record.timestamp.isoformat(),
            "actor_user_id": audit_record.actor_user_id,
            "operation": audit_record.operation,
            "payload": audit_record.payload_immutable,
            "ip_address": audit_record.ip_address,
            "user_agent": audit_record.user_agent,
        }

        # Add integrity hash
        log_entry["hash"] = self._generate_hash(log_entry)

        # Append to file (write-once)
        with open(file_path, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

        # Set file as read-only (on Unix systems)
        try:
            import os
            os.chmod(file_path, 0o444)  # Read-only for all
        except Exception:
            pass  # Windows or permission issues

        return str(file_path)

    async def verify_integrity(self, file_path: str) -> tuple[bool, List[str]]:
        """
        Verify integrity of audit log file
        Returns: (is_valid, errors)
        """
        errors = []

        try:
            with open(file_path, "r") as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())

                        # Verify hash
                        stored_hash = entry.pop("hash", None)
                        calculated_hash = self._generate_hash(entry)

                        if stored_hash != calculated_hash:
                            errors.append(
                                f"Line {line_num}: Hash mismatch (possible tampering)"
                            )

                    except json.JSONDecodeError:
                        errors.append(f"Line {line_num}: Invalid JSON")

        except FileNotFoundError:
            errors.append("Audit file not found")

        return len(errors) == 0, errors


worm_logger = WORMAuditLogger()


async def audit_log(
    actor_user_id: int,
    operation: str,
    payload: Dict[str, Any],
    session: AsyncSession,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None
) -> AuditWORM:
    """
    Create audit log entry
    This function ensures all operations are logged immutably
    """
    # Create database record
    audit_record = AuditWORM(
        timestamp=datetime.utcnow(),
        actor_user_id=actor_user_id,
        operation=operation,
        payload_immutable=payload,
        ip_address=ip_address,
        user_agent=user_agent
    )

    session.add(audit_record)
    await session.commit()
    await session.refresh(audit_record)

    # Write to immutable storage
    try:
        await worm_logger.write_to_immutable_storage(audit_record)
    except Exception as e:
        # Log error but don't fail the operation
        print(f"Warning: Failed to write to WORM storage: {e}")

    return audit_record


async def get_audit_logs(
    session: AsyncSession,
    user_id: Optional[int] = None,
    operation: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    limit: int = 100
) -> List[AuditWORM]:
    """Query audit logs (read-only)"""
    from sqlalchemy import select

    query = select(AuditWORM)

    if user_id:
        query = query.where(AuditWORM.actor_user_id == user_id)

    if operation:
        query = query.where(AuditWORM.operation == operation)

    if start_date:
        query = query.where(AuditWORM.timestamp >= start_date)

    if end_date:
        query = query.where(AuditWORM.timestamp <= end_date)

    query = query.order_by(AuditWORM.timestamp.desc()).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()
