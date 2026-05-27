"""Mission lifecycle management — spray → inspect → evaluate → retry loop."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Callable, Coroutine

from app.config_types import MuyeConfig
from app.utils import evaluate_effectiveness, parse_action_time
from modules.detection.image_processor import ImageProcessor
from modules.drone.controller import DroneController
from modules.infra.common import log_event
from modules.infra.event_bus import FileEventBus
from modules.infra.sqlite_store import SqliteStore


class MissionManager:
    """Manages the closed-loop mission lifecycle: spray → inspect → evaluate → retry."""

    def __init__(
        self,
        *,
        config: MuyeConfig,
        sqlite_store: SqliteStore,
        event_bus: FileEventBus,
        drone_controller: DroneController,
        image_processor: ImageProcessor,
        logger: logging.Logger,
        client_ip: str,
        background_tasks: set[asyncio.Task[None]],
        detect_pests_fn: Callable[..., Coroutine[Any, Any, list[dict[str, Any]]]],
        rag_index_callback: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config
        self.sqlite_store = sqlite_store
        self.event_bus = event_bus
        self.drone_controller = drone_controller
        self.image_processor = image_processor
        self.logger = logger
        self.client_ip = client_ip
        self._background_tasks = background_tasks
        self._detect_pests_fn = detect_pests_fn
        self._rag_index_callback = rag_index_callback
        self._evaluation_contexts: dict[str, dict[str, Any]] = {}

    def schedule_reinspection(
        self,
        request_id: str,
        decision: dict[str, Any],
        detections: list[dict[str, Any]],
        field_context: dict[str, Any],
        image_path: Path,
        weather: dict[str, Any] | None = None,
    ) -> None:
        """Schedule a re-inspection mission after pesticide action time elapses."""
        import uuid
        from datetime import datetime, timedelta, timezone

        medication = decision.get("用药", {})
        action_time_str = medication.get("预计见效时间", "")
        action_hours = parse_action_time(action_time_str)
        if action_hours is None:
            action_hours = self.config.evaluation_default_action_time_hours

        delay_seconds = self.config.evaluation_demo_delay_seconds
        scheduled_at = (datetime.now(timezone.utc) + timedelta(hours=action_hours)).isoformat()
        pre_pest_count = len(detections)
        threshold = self.config.evaluation_kill_rate_threshold

        crop_cycle = field_context.get("crop_cycle") or {}
        mission_uuid = str(uuid.uuid4())
        mission_row_id = self.sqlite_store.create_mission(
            mission_id=mission_uuid,
            original_request_id=request_id,
            field_id=field_context.get("field_id"),
            kill_rate_threshold=threshold,
            max_iterations=self.config.evaluation_max_retries,
            pest_types=[str(d.get("pest_type", "")) for d in detections],
            pesticide_name=medication.get("农药名称"),
            crop_name=crop_cycle.get("crop_name"),
        )

        evaluation_id = self.sqlite_store.create_evaluation(
            original_request_id=request_id,
            scheduled_at=scheduled_at,
            action_time_hours=action_hours,
            pre_pest_count=pre_pest_count,
            kill_rate_threshold=threshold,
        )

        iteration_id = self.sqlite_store.create_iteration(
            mission_id=mission_uuid,
            iteration_number=1,
            spray_request_id=request_id,
        )
        self.sqlite_store.update_iteration(
            iteration_id, evaluation_id=evaluation_id, status="spraying",
        )
        self.sqlite_store.update_mission(mission_row_id, current_iteration=1)

        self.event_bus.publish(
            request_id=request_id,
            stage="mission",
            status="created",
            message=f"任务已创建，目标杀灭率 {threshold:.0%}",
            payload={
                "mission_id": mission_uuid,
                "mission_row_id": mission_row_id,
                "iteration_id": iteration_id,
                "evaluation_id": evaluation_id,
                "action_time_hours": action_hours,
                "pre_pest_count": pre_pest_count,
                "max_iterations": self.config.evaluation_max_retries,
            },
        )
        log_event(
            self.logger, logging.INFO, "任务已创建，等待首次巡检",
            request_id=request_id, client_ip=self.client_ip,
            mission_id=mission_uuid, evaluation_id=evaluation_id,
            action_time_hours=action_hours, demo_delay_seconds=delay_seconds,
        )

        self._evaluation_contexts[request_id] = {
            "image_path": image_path,
            "field_context": field_context,
            "decision": decision,
            "detections": detections,
            "evaluation_id": evaluation_id,
            "weather": weather or {},
            "mission_row_id": mission_row_id,
            "mission_uuid": mission_uuid,
            "iteration_id": iteration_id,
            "action_hours": action_hours,
        }

        task = asyncio.create_task(self._run_mission_loop(mission_uuid, request_id, delay_seconds))
        self._background_tasks.add(task)
        task.add_done_callback(self._background_tasks.discard)

    async def _run_mission_loop(
        self, mission_uuid: str, original_request_id: str, delay_seconds: float,
    ) -> None:
        """Drive the full mission lifecycle: wait → inspect → evaluate → [re-spray → ...]."""
        try:
            await asyncio.sleep(delay_seconds)

            ctx = self._evaluation_contexts.get(original_request_id)
            if ctx is None:
                self.logger.warning("Mission context lost for %s", original_request_id)
                mission = self.sqlite_store.fetch_mission_by_mission_id(mission_uuid)
                if mission:
                    self.sqlite_store.update_mission(mission["id"], status="failed", notes="任务上下文丢失")
                return

            mission = self.sqlite_store.fetch_mission_by_mission_id(mission_uuid)
            if not mission or mission["status"] != "active":
                self.logger.info("Mission %s no longer active, skipping", mission_uuid)
                return

            kill_rate = await self._run_single_evaluation(
                ctx, original_request_id, mission_uuid, iteration_number=1,
            )
            if kill_rate is None:
                await self._abort_mission(mission_uuid, ctx, "首轮评估失败，无法计算杀灭率")
                return

            threshold = self.config.evaluation_kill_rate_threshold
            if kill_rate >= threshold:
                await self._complete_mission(mission_uuid, kill_rate, ctx)
                return

            max_iterations = self.config.evaluation_max_retries
            for iteration in range(2, max_iterations + 1):
                if not self.config.evaluation_auto_retry:
                    self.event_bus.publish(
                        request_id=original_request_id,
                        stage="mission",
                        status="retry_scheduled",
                        message=f"杀灭率 {kill_rate:.0%} 未达标，需要人工确认二次打药",
                        payload={"mission_id": mission_uuid, "kill_rate": kill_rate, "iteration": iteration - 1},
                    )
                    return

                kill_rate = await self._execute_mission_iteration(
                    ctx, original_request_id, mission_uuid, iteration,
                )
                if kill_rate is None:
                    await self._abort_mission(mission_uuid, ctx, f"第 {iteration} 轮迭代执行失败")
                    return
                if kill_rate >= threshold:
                    await self._complete_mission(mission_uuid, kill_rate, ctx)
                    return

            await self._fail_mission(mission_uuid, kill_rate, ctx)

        except Exception as exc:
            self.logger.exception("Mission loop failed for %s: %s", original_request_id, exc)
            mission = self.sqlite_store.fetch_mission_by_mission_id(mission_uuid)
            if mission:
                self.sqlite_store.update_mission(mission["id"], status="failed", notes=f"任务失败: {exc}")
            self.event_bus.publish(
                request_id=original_request_id, stage="mission", status="failed",
                message=f"任务异常终止: {exc}", payload={"mission_id": mission_uuid},
            )
            if self._rag_index_callback:
                self._rag_index_callback(mission_uuid)
        finally:
            self._evaluation_contexts.pop(original_request_id, None)

    async def _run_single_evaluation(
        self,
        ctx: dict[str, Any],
        request_id: str,
        mission_uuid: str,
        iteration_number: int,
    ) -> float | None:
        """Run inspection + YOLO evaluation for one iteration. Returns kill_rate or None on error."""
        from modules.infra.sqlite_store._private import utc_now_iso

        try:
            iteration = self.sqlite_store.fetch_latest_iteration(mission_uuid)
            if iteration is None:
                return None

            iteration_id = iteration["id"]
            evaluation_id = iteration.get("evaluation_id")

            if evaluation_id:
                eval_row = self.sqlite_store.fetch_one(
                    "SELECT status FROM task_evaluations WHERE id = ?", (evaluation_id,)
                )
                if eval_row and eval_row["status"] not in ("scheduled", "retry_scheduled"):
                    self.logger.info("Evaluation %d not in schedulable state, skipping", evaluation_id)
                    return None

            self.sqlite_store.update_iteration(iteration_id, status="inspecting", inspected_at=utc_now_iso())
            if evaluation_id:
                self.sqlite_store.update_evaluation(evaluation_id, status="inspecting", inspected_at=utc_now_iso())

            self.event_bus.publish(
                request_id=request_id,
                stage="mission",
                status="inspecting",
                message=f"第 {iteration_number} 轮巡检飞行中...",
                payload={"mission_id": mission_uuid, "iteration": iteration_number},
            )

            field_context = ctx["field_context"]
            inspection_plan = self.drone_controller.plan_inspection_mission(
                field_context=field_context,
                current_weather=ctx.get("weather", {}),
            )
            inspection_result = await self.drone_controller.execute_inspection_mission(
                request_id=request_id,
                execution_plan=inspection_plan,
                field_context=field_context,
                current_weather=ctx.get("weather", {}),
            )

            captured_images = inspection_result.get("captured_images", [])
            pre_count = len(ctx["detections"])

            original_pest_types = set()
            for det in ctx["detections"]:
                pt = str(det.get("pest_type") or det.get("label") or "").strip()
                if pt:
                    original_pest_types.add(pt)

            all_post_detections: list[dict[str, Any]] = []
            if captured_images:
                for img_path_str in captured_images:
                    img_path = Path(img_path_str)
                    if not img_path.exists():
                        continue
                    dets = await self._detect_pests_fn(request_id, img_path, publish_events=False)
                    all_post_detections.extend(dets)
            else:
                all_post_detections = await self._detect_pests_fn(request_id, ctx["image_path"], publish_events=False)

            if original_pest_types:
                post_count = sum(
                    1 for d in all_post_detections
                    if str(d.get("pest_type") or d.get("label") or "").strip() in original_pest_types
                )
            else:
                post_count = len(all_post_detections)

            kill_rate, _ = evaluate_effectiveness(
                pre_count, post_count, self.config.evaluation_kill_rate_threshold,
            )

            self.sqlite_store.update_iteration(
                iteration_id,
                status="evaluated",
                pre_pest_count=pre_count,
                post_pest_count=post_count,
                kill_rate=round(kill_rate, 4),
                captured_images=captured_images,
                evaluated_at=utc_now_iso(),
                notes=f"巡检采集 {len(captured_images)} 张; YOLO 检测 {post_count} 害虫",
            )
            if evaluation_id:
                self.sqlite_store.update_evaluation(
                    evaluation_id,
                    status="evaluated",
                    post_pest_count=post_count,
                    kill_rate=round(kill_rate, 4),
                    evaluated_at=utc_now_iso(),
                )

            self.event_bus.publish(
                request_id=request_id,
                stage="mission",
                status="evaluated",
                message=f"第 {iteration_number} 轮评估: 杀灭率 {kill_rate:.0%}",
                payload={
                    "mission_id": mission_uuid,
                    "iteration": iteration_number,
                    "kill_rate": kill_rate,
                    "pre_pest_count": pre_count,
                    "post_pest_count": post_count,
                    "captured_images": captured_images,
                },
            )
            return kill_rate

        except Exception as exc:
            self.logger.exception("Evaluation failed in iteration %d: %s", iteration_number, exc)
            return None

    async def _execute_mission_iteration(
        self,
        ctx: dict[str, Any],
        original_request_id: str,
        mission_uuid: str,
        iteration_number: int,
    ) -> float | None:
        """Execute one complete spray+inspect+evaluate cycle. Returns kill_rate or None."""
        from modules.infra.sqlite_store._private import utc_now_iso

        try:
            delay_seconds = self.config.evaluation_demo_delay_seconds

            self.event_bus.publish(
                request_id=original_request_id,
                stage="mission",
                status="spraying",
                message=f"第 {iteration_number} 轮喷洒执行中...",
                payload={"mission_id": mission_uuid, "iteration": iteration_number},
            )

            field_context = ctx["field_context"]
            decision = ctx["decision"]
            spray_plan = self.drone_controller.plan_spray_mission(
                field_context=field_context,
                current_weather=ctx.get("weather", {}),
            )
            await self.drone_controller.execute_spray_mission(
                decision=decision,
                current_weather=ctx.get("weather", {}),
                request_id=original_request_id,
                execution_plan=spray_plan,
                field_context=field_context,
            )

            evaluation_id = self.sqlite_store.create_evaluation(
                original_request_id=original_request_id,
                scheduled_at=utc_now_iso(),
                action_time_hours=ctx.get("action_hours", 24),
                pre_pest_count=len(ctx["detections"]),
                kill_rate_threshold=self.config.evaluation_kill_rate_threshold,
            )
            iteration_id = self.sqlite_store.create_iteration(
                mission_id=mission_uuid,
                iteration_number=iteration_number,
                spray_request_id=original_request_id,
            )
            self.sqlite_store.update_iteration(
                iteration_id,
                evaluation_id=evaluation_id,
                status="spraying",
                spray_completed_at=utc_now_iso(),
            )

            mission = self.sqlite_store.fetch_mission_by_mission_id(mission_uuid)
            if mission:
                self.sqlite_store.update_mission(mission["id"], current_iteration=iteration_number)

            await asyncio.sleep(delay_seconds)

            return await self._run_single_evaluation(
                ctx, original_request_id, mission_uuid, iteration_number,
            )

        except Exception as exc:
            self.logger.exception("Mission iteration %d failed: %s", iteration_number, exc)
            return None

    async def _complete_mission(
        self, mission_uuid: str, kill_rate: float, ctx: dict[str, Any],
    ) -> None:
        """Mark mission as completed and index to RAG."""
        from modules.infra.sqlite_store._private import utc_now_iso

        mission = self.sqlite_store.fetch_mission_by_mission_id(mission_uuid)
        if not mission:
            return

        self.sqlite_store.update_mission(
            mission["id"],
            status="completed",
            final_kill_rate=round(kill_rate, 4),
            total_pre_pest_count=len(ctx["detections"]),
            completed_at=utc_now_iso(),
        )

        iteration = self.sqlite_store.fetch_latest_iteration(mission_uuid)
        if iteration:
            self.sqlite_store.update_iteration(iteration["id"], status="passed")
        if iteration and iteration.get("evaluation_id"):
            self.sqlite_store.update_evaluation(iteration["evaluation_id"], status="passed")

        request_id = ctx.get("original_request_id", mission["original_request_id"])
        self.event_bus.publish(
            request_id=request_id,
            stage="mission",
            status="completed",
            message=f"任务完成，最终杀灭率 {kill_rate:.0%}",
            payload={
                "mission_id": mission_uuid,
                "kill_rate": kill_rate,
                "iterations": mission["current_iteration"],
            },
        )
        log_event(
            self.logger, logging.INFO, "任务完成",
            request_id=request_id, client_ip=self.client_ip,
            mission_id=mission_uuid, kill_rate=kill_rate,
            iterations=mission["current_iteration"],
        )

        if self._rag_index_callback:
            self._rag_index_callback(mission_uuid)

    async def _fail_mission(
        self, mission_uuid: str, kill_rate: float | None, ctx: dict[str, Any],
    ) -> None:
        """Mark mission as failed after exhausting all iterations."""
        from modules.infra.sqlite_store._private import utc_now_iso

        mission = self.sqlite_store.fetch_mission_by_mission_id(mission_uuid)
        if not mission:
            return

        self.sqlite_store.update_mission(
            mission["id"],
            status="failed",
            final_kill_rate=round(kill_rate or 0, 4),
            total_pre_pest_count=len(ctx["detections"]),
            completed_at=utc_now_iso(),
            notes=f"达到最大轮次 {mission['max_iterations']}，最终杀灭率 {kill_rate or 0:.0%}",
        )

        request_id = ctx.get("original_request_id", mission["original_request_id"])
        self.event_bus.publish(
            request_id=request_id,
            stage="mission",
            status="failed",
            message=f"任务未达标，最终杀灭率 {kill_rate or 0:.0%}",
            payload={
                "mission_id": mission_uuid,
                "kill_rate": kill_rate,
                "iterations": mission["current_iteration"],
            },
        )
        log_event(
            self.logger, logging.WARNING, "任务未达标",
            request_id=request_id, client_ip=self.client_ip,
            mission_id=mission_uuid, kill_rate=kill_rate,
            iterations=mission["current_iteration"],
        )

        if self._rag_index_callback:
            self._rag_index_callback(mission_uuid)

    async def _abort_mission(
        self, mission_uuid: str, ctx: dict[str, Any], reason: str,
    ) -> None:
        """Mark mission as failed due to an error (no kill_rate available)."""
        from modules.infra.sqlite_store._private import utc_now_iso

        mission = self.sqlite_store.fetch_mission_by_mission_id(mission_uuid)
        if not mission:
            return

        self.sqlite_store.update_mission(
            mission["id"], status="failed", completed_at=utc_now_iso(), notes=reason,
        )
        request_id = ctx.get("original_request_id", mission["original_request_id"])
        self.event_bus.publish(
            request_id=request_id, stage="mission", status="failed",
            message=reason, payload={"mission_id": mission_uuid},
        )
        log_event(
            self.logger, logging.WARNING, "任务中止",
            request_id=request_id, client_ip=self.client_ip,
            mission_id=mission_uuid, reason=reason,
        )
        if self._rag_index_callback:
            self._rag_index_callback(mission_uuid)
