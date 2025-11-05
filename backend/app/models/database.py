from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, Boolean, ForeignKey, Text, Enum as SQLEnum
from sqlalchemy.sql import func
from datetime import datetime
import enum
import hashlib

from ..core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG)
async_session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


class PlatformEnum(str, enum.Enum):
    YOUTUBE = "youtube"
    X = "x"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"


class EngineTypeEnum(str, enum.Enum):
    API_FAST = "api_fast"
    BROWSER_QA = "browser_qa"


class StatusEnum(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    EXPIRED = "expired"


class RunStatusEnum(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    ABORTED = "aborted"


# Accounts Table
class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(SQLEnum(PlatformEnum), nullable=False, index=True)
    oauth_token_ref = Column(String(255), nullable=False)  # Encrypted reference
    owner_user_id = Column(Integer, nullable=False, index=True)
    status = Column(SQLEnum(StatusEnum), default=StatusEnum.ACTIVE)
    display_name = Column(String(255))
    account_metadata = Column(JSON, default={})
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Runs Table
class Run(Base):
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    platform = Column(SQLEnum(PlatformEnum), nullable=False, index=True)
    engine = Column(SQLEnum(EngineTypeEnum), default=EngineTypeEnum.API_FAST)
    schedule_json = Column(JSON, nullable=False)  # start, end, repeat, timezone
    observability_json = Column(JSON, nullable=False)  # 16 categories thresholds
    prompt_json = Column(JSON, nullable=False)  # AI generation parameters
    rate_config = Column(JSON, nullable=False)  # hourly, daily, parallel, wait distribution
    approval_required = Column(Boolean, default=True)
    custom_prompt = Column(Text)
    status = Column(SQLEnum(RunStatusEnum), default=RunStatusEnum.PENDING, index=True)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Run Events Table
class RunEvent(Base):
    __tablename__ = "run_events"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False, index=True)
    action = Column(String(100), nullable=False)  # post, reply, like, follow
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    ended_at = Column(DateTime(timezone=True))
    response_code = Column(Integer)
    detail = Column(JSON)  # Full response, metrics
    success = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# AI Drafts Table
class AIDraft(Base):
    __tablename__ = "ai_drafts"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False)
    outputs_json = Column(JSON, nullable=False)  # drafts, schedules, hashtags
    toxicity_score = Column(Float, default=0.0)
    duplication_rate = Column(Float, default=0.0)
    approved = Column(Boolean, default=False)
    approved_by = Column(Integer)
    approved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# KPI Snapshots Table
class KPISnapshot(Base):
    __tablename__ = "kpi_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(SQLEnum(PlatformEnum), nullable=False, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"))
    range_start = Column(DateTime(timezone=True), nullable=False)
    range_end = Column(DateTime(timezone=True), nullable=False)
    metrics_json = Column(JSON, nullable=False)  # followers, engagement, reach, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# Audit WORM Table (Write-Once-Read-Many)
class AuditWORM(Base):
    __tablename__ = "audit_worm"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    actor_user_id = Column(Integer, nullable=False)
    operation = Column(String(100), nullable=False)  # create_run, approve_draft, execute_action
    payload_immutable = Column(JSON, nullable=False)  # Complete operation details
    ip_address = Column(String(45))  # IPv6 compatible
    user_agent = Column(String(500))
    hash = Column(String(64))  # SHA256 hash for integrity verification


# Observability Metrics Table
class ObservabilityMetric(Base):
    __tablename__ = "observability_metrics"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False, index=True)
    event_id = Column(Integer, ForeignKey("run_events.id"))
    category = Column(String(50), nullable=False, index=True)  # One of 16 categories
    metric_key = Column(String(100), nullable=False)
    metric_value = Column(Float, nullable=False)
    threshold_value = Column(Float)
    violated = Column(Boolean, default=False)
    action_taken = Column(String(50))  # alert, slow, freeze, abort
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)


# Campaign Table
class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    start_date = Column(DateTime(timezone=True), nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=False)
    target_metrics = Column(JSON)  # Goals and KPIs
    run_ids = Column(JSON, default=[])  # Associated runs
    status = Column(SQLEnum(RunStatusEnum), default=RunStatusEnum.PENDING)
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Kill Switch Table
class KillSwitch(Base):
    __tablename__ = "kill_switches"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("runs.id"), nullable=False, unique=True, index=True)
    is_active = Column(Boolean, default=True)
    triggered_at = Column(DateTime(timezone=True))
    triggered_by = Column(Integer)
    reason = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# Account Generation Status Enum
class AccountGenStatusEnum(str, enum.Enum):
    PENDING = "pending"  # 生成待ち
    GENERATING = "generating"  # 生成中
    VERIFICATION = "verification"  # 認証コード待ち
    COMPLETED = "completed"  # 完了
    FAILED = "failed"  # 失敗
    SUSPENDED = "suspended"  # 停止


# Account Generation Tasks Table
class AccountGenerationTask(Base):
    """アカウント自動生成タスク"""
    __tablename__ = "account_generation_tasks"

    id = Column(Integer, primary_key=True, index=True)
    platform = Column(SQLEnum(PlatformEnum), nullable=False, index=True)
    target_count = Column(Integer, nullable=False)  # 生成目標数
    completed_count = Column(Integer, default=0)  # 完了数
    failed_count = Column(Integer, default=0)  # 失敗数

    # 生成設定
    generation_config = Column(JSON, nullable=False)  # username_pattern, email_domain, phone_provider, etc.

    # プロキシ・IP設定
    proxy_list = Column(JSON, default=[])  # 使用するプロキシリスト
    use_residential_proxy = Column(Boolean, default=True)  # レジデンシャルプロキシを使用

    # ブラウザ設定
    headless = Column(Boolean, default=True)

    # 進捗
    status = Column(SQLEnum(AccountGenStatusEnum), default=AccountGenStatusEnum.PENDING, index=True)
    error_message = Column(Text)

    # メタデータ
    created_by = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


# Generated Accounts Table
class GeneratedAccount(Base):
    """自動生成されたアカウント"""
    __tablename__ = "generated_accounts"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("account_generation_tasks.id"), nullable=False, index=True)
    platform = Column(SQLEnum(PlatformEnum), nullable=False, index=True)

    # アカウント情報（暗号化）
    username = Column(String(255), nullable=False, index=True)
    email = Column(String(255), nullable=False)
    phone = Column(String(50))
    password_encrypted = Column(String(500), nullable=False)  # 暗号化されたパスワード

    # 生成時の情報
    proxy_used = Column(String(255))  # 使用したプロキシ
    ip_address = Column(String(45))  # 生成時のIPアドレス
    user_agent = Column(String(500))  # 使用したUser-Agent

    # 認証情報
    verification_code = Column(String(100))  # SMS/Email認証コード
    verification_status = Column(String(50), default="pending")  # pending, verified, failed

    # ステータス
    status = Column(SQLEnum(StatusEnum), default=StatusEnum.ACTIVE, index=True)

    # OAuth連携（生成後にOAuth認証した場合）
    oauth_token_ref = Column(String(255))  # 暗号化されたOAuthトークン参照

    # メタデータ
    generation_metadata = Column(JSON, default={})  # 生成時の詳細情報
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    verified_at = Column(DateTime(timezone=True))
    last_login = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


async def get_db():
    async with async_session_maker() as session:
        yield session
        await session.commit()


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
