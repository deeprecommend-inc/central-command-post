import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ..models.database import Run, RunEvent, ObservabilityMetric, KillSwitch, RunStatusEnum
from ..adapters.base_adapter import BaseSNSAdapter
from ..adapters.youtube_adapter import YouTubeAdapter
from ..adapters.x_adapter import XAdapter
from ..adapters.instagram_adapter import InstagramAdapter
from ..adapters.tiktok_adapter import TikTokAdapter
from ..services.redis_service import redis_service
from ..services.observability import ObservabilityMonitor, ObservabilityThreshold
from ..services.audit_service import audit_log


class ExecutionEngine:
    """Execute SNS actions with rate limiting and monitoring"""

    def __init__(self, db_session: AsyncSession):
        self.db = db_session

    def _get_adapter(self, platform: str, access_token: str, config: Optional[Dict] = None) -> BaseSNSAdapter:
        """Get appropriate adapter for platform"""
        adapters = {
            "youtube": YouTubeAdapter,
            "x": XAdapter,
            "instagram": InstagramAdapter,
            "tiktok": TikTokAdapter,
        }

        adapter_class = adapters.get(platform.lower())
        if not adapter_class:
            raise ValueError(f"Unsupported platform: {platform}")

        return adapter_class(access_token, config)

    async def _check_kill_switch(self, run_id: int) -> bool:
        """Check if run has been killed"""
        result = await self.db.execute(
            select(KillSwitch).where(
                KillSwitch.run_id == run_id,
                KillSwitch.is_active == True
            )
        )
        kill_switch = result.scalar_one_or_none()
        return kill_switch is not None

    async def _wait_with_distribution(self, rate_config: Dict[str, Any]):
        """Wait according to configured distribution"""
        min_wait = rate_config.get("wait_min_seconds", 10)
        max_wait = rate_config.get("wait_max_seconds", 60)
        distribution = rate_config.get("distribution", "uniform")

        if distribution == "normal":
            # Normal distribution
            mean = (min_wait + max_wait) / 2
            std = (max_wait - min_wait) / 6  # 99.7% within range
            wait_time = random.gauss(mean, std)
            wait_time = max(min_wait, min(max_wait, wait_time))
        else:
            # Uniform distribution
            wait_time = random.uniform(min_wait, max_wait)

        await asyncio.sleep(wait_time)

    async def _record_event(
        self,
        run_id: int,
        action: str,
        response: Any,
        started_at: datetime
    ) -> RunEvent:
        """Record execution event"""
        event = RunEvent(
            run_id=run_id,
            action=action,
            started_at=started_at,
            ended_at=datetime.utcnow(),
            response_code=response.response_code if hasattr(response, 'response_code') else 0,
            detail=response.to_dict() if hasattr(response, 'to_dict') else {},
            success=response.success if hasattr(response, 'success') else False
        )

        self.db.add(event)
        await self.db.commit()
        await self.db.refresh(event)

        return event

    async def _check_observability(
        self,
        run_id: int,
        thresholds: ObservabilityThreshold,
        metrics: Dict[str, Dict[str, float]]
    ) -> tuple[bool, str]:
        """
        Check observability metrics
        Returns: (should_continue, action_taken)
        """
        monitor = ObservabilityMonitor(thresholds)
        violations, action = monitor.evaluate_all(metrics)

        # Record violations
        for violation in violations:
            metric_record = ObservabilityMetric(
                run_id=run_id,
                category=violation["category"],
                metric_key=violation["metric_key"],
                metric_value=violation["value"],
                threshold_value=violation["threshold"],
                violated=True,
                action_taken=str(action.value)
            )
            self.db.add(metric_record)

        await self.db.commit()

        # Determine if should continue
        if action.value == "abort":
            return False, "abort"
        elif action.value == "freeze":
            return False, "freeze"
        elif action.value == "slow":
            return True, "slow"
        else:
            return True, "alert"

    async def execute_action(
        self,
        run_id: int,
        account_id: int,
        platform: str,
        action: str,
        access_token: str,
        action_params: Dict[str, Any],
        rate_config: Dict[str, Any],
        observability_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single action"""
        started_at = datetime.utcnow()

        # Check kill switch
        if await self._check_kill_switch(run_id):
            return {
                "success": False,
                "error": "Run has been killed",
                "action": "kill_switch"
            }

        # Check rate limits
        hourly_limit = rate_config.get("hourly_limit", 100)
        daily_limit = rate_config.get("daily_limit", 1000)

        rate_allowed, reason = await redis_service.check_platform_rate(
            platform,
            account_id,
            action,
            hourly_limit,
            daily_limit
        )

        if not rate_allowed:
            return {
                "success": False,
                "error": reason,
                "action": "rate_limit"
            }

        # Wait according to distribution
        await self._wait_with_distribution(rate_config)

        # Get adapter and execute
        try:
            adapter = self._get_adapter(platform, access_token, action_params.get("config"))

            # Execute action
            if action == "post":
                response = await adapter.post(
                    action_params.get("content", ""),
                    **action_params
                )
            elif action == "reply":
                response = await adapter.reply(
                    action_params.get("post_id"),
                    action_params.get("content", ""),
                    **action_params
                )
            elif action == "like":
                response = await adapter.like(action_params.get("post_id"))
            elif action == "follow":
                response = await adapter.follow(action_params.get("user_id"))
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}"
                }

            # Record event
            await self._record_event(run_id, action, response, started_at)

            # Check observability (if metrics provided)
            if "metrics" in action_params:
                thresholds = ObservabilityThreshold.from_dict(observability_config)
                should_continue, obs_action = await self._check_observability(
                    run_id,
                    thresholds,
                    action_params["metrics"]
                )

                if not should_continue:
                    return {
                        "success": False,
                        "error": f"Observability violation: {obs_action}",
                        "action": obs_action,
                        "response": response.to_dict()
                    }

            return {
                "success": response.success,
                "response": response.to_dict(),
                "action": "executed"
            }

        except Exception as e:
            # Record failed event
            error_response = type('ErrorResponse', (), {
                'response_code': 500,
                'success': False,
                'to_dict': lambda: {'error': str(e)}
            })()

            await self._record_event(run_id, action, error_response, started_at)

            return {
                "success": False,
                "error": str(e),
                "action": "exception"
            }


class WorkerScheduler:
    """Schedule and manage worker jobs"""

    def __init__(self):
        self.running = False

    async def start(self):
        """Start worker scheduler"""
        self.running = True

        print("Worker scheduler started. Waiting for jobs...")

        while self.running:
            try:
                # Dequeue job from Redis
                job = await redis_service.dequeue_job("execution_queue")

                if job:
                    print(f"Processing job: {job.get('action')} for run_id: {job.get('run_id')}")
                    await self._process_job(job)
                else:
                    # No jobs, wait a bit
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"Error in worker loop: {e}")
                await asyncio.sleep(5)

    async def stop(self):
        """Stop worker scheduler"""
        print("Stopping worker scheduler...")
        self.running = False

    async def _process_job(self, job: Dict[str, Any]):
        """Process a single job"""
        from ..models.database import async_session_maker

        async with async_session_maker() as session:
            engine = ExecutionEngine(session)

            result = await engine.execute_action(
                run_id=job["run_id"],
                account_id=job["account_id"],
                platform=job["platform"],
                action=job["action"],
                access_token=job["access_token"],
                action_params=job["action_params"],
                rate_config=job["rate_config"],
                observability_config=job["observability_config"]
            )

            # Log to audit
            await audit_log(
                actor_user_id=job.get("user_id", 0),
                operation=f"execute_{job['action']}",
                payload={
                    "run_id": job["run_id"],
                    "result": result
                },
                session=session
            )


# Main entry point for worker
async def main():
    """Main worker entry point"""
    print("Starting SNS Orchestrator Worker...")

    # Connect to Redis
    await redis_service.connect()
    print("Connected to Redis")

    # Start scheduler
    scheduler = WorkerScheduler()
    try:
        await scheduler.start()
    except KeyboardInterrupt:
        print("\nReceived interrupt signal")
        await scheduler.stop()
    finally:
        await redis_service.disconnect()
        print("Worker stopped")


if __name__ == "__main__":
    import sys
    print(f"Python version: {sys.version}")
    print(f"Starting worker process...")

    try:
        asyncio.run(main())
    except Exception as e:
        print(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
