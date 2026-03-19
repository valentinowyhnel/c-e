from __future__ import annotations

from typing import Any

import httpx

from ..logging import get_logger

log = get_logger(__name__)


class BloodHoundGuard:
    """
    Garde lecture-seule BloodHound CE avant chaque action AD sensible.
    """

    def __init__(self, api_token: str, base_url: str = "http://bloodhound-ce:8080"):
        self._client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Authorization": f"Bearer {api_token}"},
            timeout=10.0,
        )

    async def close(self) -> None:
        await self._client.aclose()

    async def check_attack_path(self, from_object: str, to_object: str) -> dict[str, Any]:
        try:
            resp = await self._client.get("/api/v2/attack-paths", params={"source": from_object, "target": to_object})
            resp.raise_for_status()
            data = resp.json()
            paths = data.get("data", {}).get("paths", [])
            return {
                "has_path": len(paths) > 0,
                "path_count": len(paths),
                "shortest": paths[0] if paths else None,
                "risk_level": 5 if paths else 0,
            }
        except Exception as exc:
            log.error("bloodhound.check.error", error=str(exc)[:200])
            return {"has_path": True, "path_count": -1, "risk_level": 3, "error": str(exc)}

    async def get_tier0_assets(self) -> list[str]:
        try:
            resp = await self._client.get("/api/v2/domains/default/tier-zero")
            resp.raise_for_status()
            return [asset["objectid"] for asset in resp.json().get("data", [])]
        except Exception as exc:
            log.error("bloodhound.tier0.error", error=str(exc)[:200])
            return []

    async def check_group_membership_risk(self, account_sid: str, target_group_dn: str) -> dict[str, Any]:
        tier0 = await self.get_tier0_assets()
        if target_group_dn in tier0:
            return {
                "risk_level": 5,
                "reason": "target_group_is_tier0",
                "action": "deny_automatic_add_human_required",
            }
        for tier0_asset in tier0:
            path = await self.check_attack_path(target_group_dn, tier0_asset)
            if path["has_path"]:
                return {
                    "risk_level": 4,
                    "reason": f"group_has_path_to_tier0_{tier0_asset[:20]}",
                    "action": "requires_approval",
                    "path": path.get("shortest"),
                    "account_sid": account_sid,
                }
        return {"risk_level": 1, "reason": "no_tier0_path", "action": "allow"}

    async def get_privilege_path_summary(self, source: str, target: str) -> dict[str, Any]:
        path = await self.check_attack_path(source, target)
        summary = "no_path"
        if path["has_path"]:
            summary = "direct_or_indirect_path_to_target"
        return {
            "source": source,
            "target": target,
            "summary": summary,
            "has_path": path["has_path"],
            "path_count": path["path_count"],
            "shortest": path.get("shortest"),
            "risk_level": path["risk_level"],
        }

    async def get_resource_exposure(self, object_id: str) -> dict[str, Any]:
        tier0 = await self.get_tier0_assets()
        risky_paths = []
        for asset in tier0[:10]:
            path = await self.check_attack_path(object_id, asset)
            if path["has_path"]:
                risky_paths.append(
                    {
                        "target": asset,
                        "path_count": path["path_count"],
                        "shortest": path.get("shortest"),
                        "risk_level": path["risk_level"],
                    }
                )
        return {
            "object_id": object_id,
            "reachable_tier0_assets": len(risky_paths),
            "paths": risky_paths,
            "risk_level": max((item["risk_level"] for item in risky_paths), default=0),
        }

    async def answer_privilege_question(self, subject: str, question: str, target: str | None = None) -> dict[str, Any]:
        normalized = question.lower()
        if "tier 0" in normalized or "admin" in normalized or target:
            resolved_target = target or "tier0"
            summary = await self.get_privilege_path_summary(subject, resolved_target)
            return {"subject": subject, "question": question, "answer_type": "privilege_path", **summary}
        exposure = await self.get_resource_exposure(subject)
        return {"subject": subject, "question": question, "answer_type": "resource_exposure", **exposure}

    async def get_blast_radius(self, object_id: str) -> dict[str, Any]:
        exposure = await self.get_resource_exposure(object_id)
        return {
            "entity_id": object_id,
            "reachable_tier0_assets": exposure["reachable_tier0_assets"],
            "critical_paths": exposure["paths"][:5],
            "risk_level": exposure["risk_level"],
            "summary": "bloodhound_blast_radius",
        }
