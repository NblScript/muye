"""Demo readiness aggregation for presentation-time diagnostics."""

from __future__ import annotations

from typing import Any


Status = str


def _status_from_health(value: dict[str, Any] | None) -> Status:
    raw = str((value or {}).get("status") or "").lower()
    if raw == "ok":
        return "ok"
    if raw in {"skipped", "warning"}:
        return "warning"
    return "error"


def _issue(
    *,
    key: str,
    label: str,
    status: Status,
    detail: str,
    reason: str,
    impact: str,
    system_action: str,
    human_action: str,
) -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
        "reason": reason,
        "impact": impact,
        "system_action": system_action,
        "human_action": human_action,
    }


def _check(
    *,
    key: str,
    label: str,
    status: Status,
    detail: str,
    reason: str = "",
    impact: str = "",
    system_action: str = "",
    human_action: str = "",
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": key,
        "label": label,
        "status": status,
        "detail": detail,
    }
    if status != "ok":
        payload.update(
            _issue(
                key=key,
                label=label,
                status=status,
                detail=detail,
                reason=reason,
                impact=impact,
                system_action=system_action,
                human_action=human_action,
            )
        )
    return payload


def _task_has_decision(latest_task: dict[str, Any]) -> bool:
    decision = latest_task.get("decision") if isinstance(latest_task, dict) else {}
    medication = (decision or {}).get("用药") if isinstance(decision, dict) else {}
    return isinstance(medication, dict) and bool(medication.get("农药名称"))


def build_demo_readiness_response(
    *,
    health: dict[str, Any],
    workflow: dict[str, Any],
    websocket_connected: bool | None = None,
) -> dict[str, Any]:
    """Build a frontend-friendly readiness model from health and workflow state."""
    health_checks = health.get("checks") or {}
    latest_task = workflow.get("latest_task") or {}
    rag_context = latest_task.get("rag_context") or {}
    consultation = rag_context.get("consultation_detail") or {}
    active_experts = int(consultation.get("active_count") or len(consultation.get("experts") or {}))
    px4 = health_checks.get("px4_runtime") or {}

    checks = {
        "backend": _check(
            key="backend",
            label="后端",
            status="ok" if health_checks else "error",
            detail="在线" if health_checks else "健康检查不可用",
            reason="后端健康检查未返回可用结果",
            impact="前端无法判断演示链路状态",
            system_action="保留页面轮询和局部错误提示",
            human_action="检查 FastAPI 服务和 /health 接口",
        ),
        "database": _check(
            key="database",
            label="SQLite",
            status=_status_from_health(health_checks.get("sqlite")),
            detail=str((health_checks.get("sqlite") or {}).get("path") or "数据库检查"),
            reason="SQLite 查询失败或路径不可用",
            impact="最新任务、历史记录和演示种子数据可能缺失",
            system_action="前端会展示降级状态，后端保留 fallback 工作流",
            human_action="检查 MUYE_SQLITE_PATH 和数据库文件权限",
        ),
        "yolo": _check(
            key="yolo",
            label="YOLO",
            status=_status_from_health(health_checks.get("yolo_model")),
            detail=str((health_checks.get("yolo_model") or {}).get("active_model") or "模型检查"),
            reason="YOLO 模型文件不可用",
            impact="无法生成稳定的虫情识别结果",
            system_action="演示可继续展示已有种子任务",
            human_action="检查 config/yolo_config.yaml 和模型路径",
        ),
        "qwen": _check(
            key="qwen",
            label="LLM",
            status=_status_from_health(health_checks.get("ai_config")),
            detail=str((health_checks.get("ai_config") or {}).get("qwen_mode") or "千问配置"),
            reason="千问密钥或 mock 配置不可用",
            impact="AI 决策和专家会诊无法实时生成",
            system_action="优先展示已持久化决策或演示种子数据",
            human_action="检查 QWEN_API_KEY 或 QWEN_USE_MOCK",
        ),
        "rag": _check(
            key="rag",
            label="RAG",
            status=_status_from_health(health_checks.get("rag_config")),
            detail="已启用" if (health_checks.get("rag_config") or {}).get("enabled") else "未启用",
            reason="RAG 配置或向量库依赖不可用",
            impact="候选药剂和知识依据可能不完整",
            system_action="合规链路会要求人工复核来源",
            human_action="检查 RAG_ENABLED、QWEN_API_KEY 和 Chroma 数据",
        ),
        "weather": _check(
            key="weather",
            label="天气",
            status=_status_from_health(health_checks.get("weather_config")),
            detail=str((health_checks.get("weather_config") or {}).get("mode") or "天气配置"),
            reason="天气 API 或 mock 配置不可用",
            impact="天气约束无法参与施药决策",
            system_action="合规检查会标记天气来源需复核",
            human_action="检查 QWEATHER_API_KEY 或 QWEATHER_USE_MOCK",
        ),
        "latest_task": _check(
            key="latest_task",
            label="最新任务",
            status="ok" if latest_task.get("request_id") else "warning",
            detail=str(latest_task.get("request_id") or "等待任务"),
            reason="当前没有可展示的完整任务",
            impact="Dashboard 只能显示空态或 fallback 流程",
            system_action="保留上传入口和 fallback 状态",
            human_action="运行 scripts/seed_demo_state.sh 或上传巡检图片",
        ),
        "decision": _check(
            key="decision",
            label="AI 决策",
            status="ok" if _task_has_decision(latest_task) else "warning",
            detail="已生成" if _task_has_decision(latest_task) else "等待决策",
            reason="最新任务缺少用药方案",
            impact="无法展示完整施药闭环",
            system_action="前端展示等待决策状态",
            human_action="检查 LLM/RAG 配置或重新注入演示任务",
        ),
        "multi_agent": _check(
            key="multi_agent",
            label="多智能体",
            status="ok" if active_experts > 0 else "warning",
            detail=f"{active_experts} 位专家" if active_experts > 0 else "未触发",
            reason="最新任务缺少多智能体会诊详情",
            impact="评委无法看到专家协同推理过程",
            system_action="保留单模型决策展示",
            human_action="启用 MUYE_MULTI_AGENT_ENABLED 或使用演示种子任务",
        ),
        "px4": _check(
            key="px4",
            label="PX4",
            status="ok" if px4.get("ready") else "warning",
            detail="已就绪" if px4.get("ready") else "未就绪",
            reason="PX4 进程未启动或 MAVLink 端口未就绪",
            impact="真实 PX4 执行动画可能不可用",
            system_action="切换为 animated_demo 或展示已记录任务状态",
            human_action="点击启动 PX4 仿真，或检查 PX4 安装路径",
        ),
        "websocket": _check(
            key="websocket",
            label="WebSocket",
            status="ok" if websocket_connected is True else "warning",
            detail="实时" if websocket_connected is True else "轮询",
            reason="WebSocket 未确认连接",
            impact="地图和任务状态可能有 1-2 秒延迟",
            system_action="前端自动降级为 HTTP 轮询",
            human_action="一般无需处理；若长期异常，刷新页面",
        ),
    }

    issues = [
        item
        for item in checks.values()
        if item["status"] in {"warning", "error"}
    ]
    status = "ready"
    if any(item["status"] == "error" for item in issues):
        status = "degraded"
    if any(item["key"] in {"backend", "database"} and item["status"] == "error" for item in issues):
        status = "blocked"
    elif issues and status == "ready":
        status = "degraded"

    return {
        "status": status,
        "summary": {
            "ok": sum(1 for item in checks.values() if item["status"] == "ok"),
            "warning": sum(1 for item in checks.values() if item["status"] == "warning"),
            "error": sum(1 for item in checks.values() if item["status"] == "error"),
        },
        "checks": checks,
        "issues": issues,
    }
