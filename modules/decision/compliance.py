"""Pesticide compliance reasoning chain built on top of retrieved RAG context."""

from __future__ import annotations

import re
from typing import Any

from modules.decision.rag.retriever import PEST_SYNONYMS

CHECK_NAMES: dict[str, str] = {
    "source_match": "来源验证",
    "crop_match": "作物适用性",
    "pest_match": "防治对象匹配",
    "toxicity_risk": "毒性安全",
    "weather_risk": "天气约束",
}

STATUS_LABELS: dict[str, str] = {
    "passed": "合规通过",
    "warning": "风险提示",
    "blocked": "已拦截",
}


class PesticideComplianceChecker:
    """Validate an AI pesticide recommendation against retrieved catalog facts."""

    def check(
        self,
        *,
        decision: dict[str, Any],
        rag_context: dict[str, Any] | None,
        field_context: dict[str, Any],
        pest_detections: list[dict[str, Any]],
        weather: dict[str, Any],
    ) -> dict[str, Any]:
        pesticide_name = self._pesticide_name(decision)
        candidate = self._find_candidate(pesticide_name, rag_context or {})
        crop_name = self._crop_name(field_context, rag_context or {})
        pest_terms = self._pest_terms(pest_detections, rag_context or {})

        checks = [
            self._check_source_match(pesticide_name, candidate),
            self._check_crop_match(pesticide_name, crop_name, candidate),
            self._check_pest_match(pesticide_name, pest_terms, candidate),
            self._check_toxicity(pesticide_name, candidate),
            self._check_weather(weather),
        ]

        blocking_reasons = [
            str(item["message"]) for item in checks if item["status"] == "blocked"
        ]
        warnings: list[str] = []
        for item in checks:
            if item["status"] == "warning":
                warnings.extend(self._split_warning_message(str(item["message"])))

        status = "passed"
        if blocking_reasons:
            status = "blocked"
        elif warnings:
            status = "warning"

        score = self._score(checks)
        summary = self._build_summary(status, pesticide_name, blocking_reasons, warnings)

        if status == "blocked":
            takeoff_mode = "blocked"
        elif status == "warning":
            takeoff_mode = "manual"
        else:
            takeoff_mode = "auto"

        return {
            "status": status,
            "score": score,
            "summary": summary,
            "checks": checks,
            "blocking_reasons": blocking_reasons,
            "warnings": warnings,
            "execution_policy": {
                "takeoff_mode": takeoff_mode,
                "reason": summary,
            },
            "alternatives": [],
        }

    # ── Check implementations ──

    def _check_source_match(
        self,
        pesticide_name: str,
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if candidate is None:
            return {
                "rule": "source_match",
                "name": CHECK_NAMES["source_match"],
                "status": "warning",
                "message": f"未在 RAG 农药候选中找到{pesticide_name or '推荐药剂'}，需要人工复核来源",
                "evidence": [],
            }
        evidence = self._build_evidence(candidate, ["product_name", "active_ingredient"])
        return {
            "rule": "source_match",
            "name": CHECK_NAMES["source_match"],
            "status": "passed",
            "message": f"{pesticide_name}来自 RAG 农药候选",
            "evidence": evidence,
        }

    def _check_crop_match(
        self,
        pesticide_name: str,
        crop_name: str,
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        crops = self._candidate_terms(candidate, "target_crops", "适用作物")
        if not candidate or not crop_name or not crops:
            return {
                "rule": "crop_match",
                "name": CHECK_NAMES["crop_match"],
                "status": "warning",
                "message": f"{pesticide_name or '推荐药剂'}缺少作物适用性数据，需人工确认",
                "evidence": [],
            }
        matched = any(self._soft_match(crop_name, crop) for crop in crops)
        evidence = self._build_evidence(candidate, ["target_crops"])
        if matched:
            return {
                "rule": "crop_match",
                "name": CHECK_NAMES["crop_match"],
                "status": "passed",
                "message": f"{pesticide_name}适用于当前作物{crop_name}",
                "evidence": evidence,
            }
        return {
            "rule": "crop_match",
            "name": CHECK_NAMES["crop_match"],
            "status": "blocked",
            "message": f"当前作物{crop_name}不在{pesticide_name}适用作物范围内",
            "evidence": evidence,
        }

    def _check_pest_match(
        self,
        pesticide_name: str,
        pest_terms: list[str],
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        target_pests = self._candidate_terms(candidate, "target_pests", "防治对象")
        if not candidate or not pest_terms or not target_pests:
            return {
                "rule": "pest_match",
                "name": CHECK_NAMES["pest_match"],
                "status": "warning",
                "message": f"{pesticide_name or '推荐药剂'}缺少防治对象数据，需人工确认",
                "evidence": [],
            }
        matched = any(
            self._soft_match(pest, target)
            for pest in pest_terms
            for target in target_pests
        )
        evidence = self._build_evidence(candidate, ["target_pests"])
        if matched:
            return {
                "rule": "pest_match",
                "name": CHECK_NAMES["pest_match"],
                "status": "passed",
                "message": f"{pesticide_name}覆盖当前检测害虫",
                "evidence": evidence,
            }
        return {
            "rule": "pest_match",
            "name": CHECK_NAMES["pest_match"],
            "status": "blocked",
            "message": f"检测害虫与{pesticide_name}防治对象不匹配",
            "evidence": evidence,
        }

    def _check_toxicity(
        self,
        pesticide_name: str,
        candidate: dict[str, Any] | None,
    ) -> dict[str, Any]:
        toxicity = self._candidate_text(candidate, "toxicity", "毒性")
        evidence = self._build_evidence(candidate, ["toxicity"]) if candidate else []
        if not toxicity:
            return {
                "rule": "toxicity_risk",
                "name": CHECK_NAMES["toxicity_risk"],
                "status": "warning",
                "message": f"{pesticide_name or '推荐药剂'}缺少毒性信息，需人工复核",
                "evidence": evidence,
            }
        if "剧毒" in toxicity or "高毒" in toxicity:
            return {
                "rule": "toxicity_risk",
                "name": CHECK_NAMES["toxicity_risk"],
                "status": "blocked",
                "message": f"{pesticide_name}毒性为{toxicity}，禁止进入自动喷洒",
                "evidence": evidence,
            }
        if "中等毒" in toxicity or "中毒" in toxicity:
            return {
                "rule": "toxicity_risk",
                "name": CHECK_NAMES["toxicity_risk"],
                "status": "warning",
                "message": f"{pesticide_name}毒性为{toxicity}，执行前需要人工复核",
                "evidence": evidence,
            }
        return {
            "rule": "toxicity_risk",
            "name": CHECK_NAMES["toxicity_risk"],
            "status": "passed",
            "message": f"{pesticide_name}毒性为{toxicity}",
            "evidence": evidence,
        }

    def _check_weather(self, weather: dict[str, Any]) -> dict[str, Any]:
        wind_speed = self._number(weather.get("wind_speed") or weather.get("windSpeed"))
        humidity = self._number(weather.get("humidity"))
        matched_fields: list[str] = []
        if wind_speed is not None:
            matched_fields.append("wind_speed")
        if humidity is not None:
            matched_fields.append("humidity")
        evidence = [{"source": "weather_api", "title": "实时气象", "matched_fields": matched_fields}] if matched_fields else []

        if wind_speed is not None and wind_speed >= 8:
            return {
                "rule": "weather_risk",
                "name": CHECK_NAMES["weather_risk"],
                "status": "blocked",
                "message": f"当前风速{wind_speed:g}m/s过高，禁止自动喷洒",
                "evidence": evidence,
            }
        weather_warnings: list[str] = []
        if wind_speed is not None and wind_speed > 5:
            weather_warnings.append(f"当前风速{wind_speed:g}m/s偏高，注意药液漂移风险")
        if humidity is not None and humidity >= 85:
            weather_warnings.append(f"当前湿度{humidity:g}%偏高，建议避开降雨或露水窗口")
        if humidity is not None and humidity < 35:
            weather_warnings.append(f"当前湿度{humidity:g}%偏低，注意药液蒸发风险")
        if weather_warnings:
            return {
                "rule": "weather_risk",
                "name": CHECK_NAMES["weather_risk"],
                "status": "warning",
                "message": "；".join(weather_warnings),
                "evidence": evidence,
            }
        return {
            "rule": "weather_risk",
            "name": CHECK_NAMES["weather_risk"],
            "status": "passed",
            "message": "当前天气条件未触发施药风险",
            "evidence": evidence,
        }

    # ── Summary builder ──

    def _build_summary(
        self,
        status: str,
        pesticide_name: str,
        blocking_reasons: list[str],
        warnings: list[str],
    ) -> str:
        name = pesticide_name or "推荐药剂"
        if status == "blocked":
            reasons = "；".join(blocking_reasons[:2])
            return f"{STATUS_LABELS[status]}：{reasons}"
        if status == "warning":
            items = "；".join(warnings[:3])
            return f"{STATUS_LABELS[status]}：{name}存在风险——{items}"
        return f"{STATUS_LABELS[status]}：{name}通过全部合规检查"

    # ── Evidence builder ──

    def _build_evidence(
        self,
        candidate: dict[str, Any] | None,
        relevant_keys: list[str],
    ) -> list[dict[str, Any]]:
        if not candidate:
            return []
        metadata = candidate.get("metadata")
        source = ""
        title = ""
        if isinstance(metadata, dict):
            source = str(metadata.get("source") or "")
            title = str(metadata.get("product_name") or metadata.get("active_ingredient") or "")
        if not source:
            source = "pesticide_catalog"
        if not title:
            content = str(candidate.get("content") or "")
            first_line = content.split("\n")[0] if content else ""
            title = first_line[:40] if first_line else "未知来源"
        matched: list[str] = []
        if isinstance(metadata, dict):
            for key in relevant_keys:
                if metadata.get(key) is not None:
                    matched.append(key)
        if not matched:
            content = str(candidate.get("content") or "")
            for key in relevant_keys:
                label_map = {"target_crops": "适用作物", "target_pests": "防治对象", "toxicity": "毒性"}
                label = label_map.get(key, key)
                if label in content:
                    matched.append(key)
        return [{"source": source, "title": title, "matched_fields": matched}]

    # ── Scoring ──

    def _score(self, checks: list[dict[str, Any]]) -> int:
        score = 100
        for item in checks:
            if item["status"] == "blocked":
                score -= 35
            elif item["status"] == "warning":
                score -= 12
        return max(0, score)

    # ── Helpers ──

    def _pesticide_name(self, decision: dict[str, Any]) -> str:
        medication = decision.get("用药")
        if not isinstance(medication, dict):
            return ""
        return str(medication.get("农药名称") or "").strip()

    def _find_candidate(
        self,
        pesticide_name: str,
        rag_context: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not pesticide_name:
            return None
        for candidate in rag_context.get("pesticides", []) or []:
            if not isinstance(candidate, dict):
                continue
            names = [
                self._candidate_text(candidate, "product_name", "农药名称"),
                self._candidate_text(candidate, "active_ingredient", "有效成分"),
                str(candidate.get("content") or ""),
            ]
            if any(pesticide_name in name for name in names if name):
                return candidate
        return None

    def _crop_name(self, field_context: dict[str, Any], rag_context: dict[str, Any]) -> str:
        crop_cycle = field_context.get("crop_cycle")
        if isinstance(crop_cycle, dict):
            crop_name = str(crop_cycle.get("crop_name") or "").strip()
            if crop_name:
                return crop_name
        return str(rag_context.get("crop_name") or "").strip()

    def _pest_terms(
        self,
        pest_detections: list[dict[str, Any]],
        rag_context: dict[str, Any],
    ) -> list[str]:
        raw_terms = [
            str(item.get("pest_type") or "").strip()
            for item in pest_detections
            if str(item.get("pest_type") or "").strip()
        ]
        if not raw_terms:
            raw_terms.extend(
                str(item).strip()
                for item in rag_context.get("pest_types", []) or []
                if str(item).strip()
            )
        terms: list[str] = []
        seen: set[str] = set()
        for term in raw_terms:
            aliases = PEST_SYNONYMS.get(self._canonical_pest(term), (term,))
            for alias in aliases:
                normalized = alias.strip()
                if normalized and normalized not in seen:
                    seen.add(normalized)
                    terms.append(normalized)
        return terms

    def _canonical_pest(self, pest_type: str) -> str:
        token = pest_type.strip().lower()
        for canonical, aliases in PEST_SYNONYMS.items():
            if token == canonical or token in {alias.lower() for alias in aliases}:
                return canonical
        return token

    def _candidate_terms(
        self,
        candidate: dict[str, Any] | None,
        metadata_key: str,
        content_label: str,
    ) -> list[str]:
        if not candidate:
            return []
        metadata = candidate.get("metadata")
        value = metadata.get(metadata_key) if isinstance(metadata, dict) else None
        if value is None:
            value = self._content_field(str(candidate.get("content") or ""), content_label)
        return self._split_terms(value)

    def _candidate_text(
        self,
        candidate: dict[str, Any] | None,
        metadata_key: str,
        content_label: str,
    ) -> str:
        if not candidate:
            return ""
        metadata = candidate.get("metadata")
        value = metadata.get(metadata_key) if isinstance(metadata, dict) else None
        if value is None:
            value = self._content_field(str(candidate.get("content") or ""), content_label)
        if isinstance(value, list):
            return "、".join(str(item) for item in value)
        return str(value or "").strip()

    def _content_field(self, content: str, label: str) -> str:
        match = re.search(rf"{re.escape(label)}[:：]([^\n]+)", content)
        return match.group(1).strip() if match else ""

    def _split_terms(self, value: Any) -> list[str]:
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        text = str(value or "")
        return [
            item.strip()
            for item in re.split(r"[、,，;；\s]+", text)
            if item.strip()
        ]

    def _split_warning_message(self, message: str) -> list[str]:
        return [item.strip() for item in message.split("；") if item.strip()]

    def _soft_match(self, left: str, right: str) -> bool:
        left_normalized = left.strip().lower()
        right_normalized = right.strip().lower()
        if not left_normalized or not right_normalized:
            return False
        return left_normalized in right_normalized or right_normalized in left_normalized

    def _number(self, value: Any) -> float | None:
        if isinstance(value, int | float):
            return float(value)
        match = re.search(r"-?\d+(?:\.\d+)?", str(value or ""))
        return float(match.group(0)) if match else None
