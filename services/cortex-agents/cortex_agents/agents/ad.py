from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from ..ad.action_verifier import ADActionVerifier
from ..ad.bloodhound_guard import BloodHoundGuard
from ..ad.drift_detector import ADSnapshot, ADDriftDetector
from ..ad.kerberos_validator import KerberosValidator
from ..ad.ldap_client import CortexLDAPClient
from ..base import AgentResult, CortexBaseAgent

ROOT = Path(__file__).resolve().parents[4] / "shared" / "cortex-core"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cortex_core.contracts import CapabilityMaturity, ExecutionMode  # noqa: E402


class ADAgent(CortexBaseAgent):
    """
    Agent AD v2: pre-check BloodHound, validation Kerberos, écriture LDAP,
    vérification post-action et scans de dérive dans le temps.
    """

    def __init__(self):
        super().__init__("ad")
        self.ldap = self._build_ldap()
        self.bh_guard = self._build_bloodhound_guard()
        self.krb_val = KerberosValidator()
        self.verifier = ADActionVerifier(self.ldap) if self.ldap else None
        self.drift_det = ADDriftDetector(self.ldap) if self.ldap else None

    def _build_ldap(self) -> CortexLDAPClient | None:
        dc_host = os.getenv("AD_DC_HOST")
        domain = os.getenv("AD_DOMAIN")
        username = os.getenv("AD_USERNAME")
        password = os.getenv("AD_PASSWORD")
        if not all([dc_host, domain, username, password]):
            return None
        client = CortexLDAPClient(dc_host=dc_host, domain=domain, username=username, password=password)
        client.connect()
        return client

    def _build_bloodhound_guard(self) -> BloodHoundGuard | None:
        token = os.getenv("BLOODHOUND_API_TOKEN")
        if not token:
            return None
        return BloodHoundGuard(api_token=token)

    async def execute(self, task: dict) -> AgentResult:
        handlers = {
            "create_user": self._create_user,
            "disable_account": self._disable_account,
            "add_to_group": self._add_to_group,
            "remove_from_group": self._remove_from_group,
            "reset_password": self._reset_password,
            "move_to_ou": self._move_to_ou,
            "create_service_account": self._create_service_account,
            "run_drift_scan": self._run_drift_scan,
            "restore_deleted": self._restore_deleted,
            "get_attack_path": self._get_attack_path,
            "get_blast_radius": self._get_blast_radius,
            "answer_privilege_question": self._answer_privilege_question,
            "visualize_exposure": self._visualize_exposure,
            "get_tier0_assets": self._get_tier0_assets,
            "validate_group_membership": self._validate_group_membership,
            "validate_service_account": self._validate_service_account,
            "get_object_acl": self._get_object_acl,
            "get_deleted_objects": self._get_deleted_objects,
            "dirsync_changes": self._dirsync_changes,
        }
        handler = handlers.get(task.get("type", ""))
        if not handler:
            return self._error_result(task, f"Unknown task: {task.get('type', '')}")
        return await handler(task)

    async def _create_user(self, task: dict) -> AgentResult:
        return self._error_result(task, "create_user not yet implemented in ADAgent v2")

    async def _disable_account(self, task: dict) -> AgentResult:
        return self._error_result(task, "disable_account not yet implemented in ADAgent v2")

    async def _remove_from_group(self, task: dict) -> AgentResult:
        return self._error_result(task, "remove_from_group not yet implemented in ADAgent v2")

    async def _reset_password(self, task: dict) -> AgentResult:
        return self._error_result(task, "reset_password not yet implemented in ADAgent v2")

    async def _move_to_ou(self, task: dict) -> AgentResult:
        return self._error_result(task, "move_to_ou not yet implemented in ADAgent v2")

    async def _add_to_group(self, task: dict) -> AgentResult:
        account_dn = task["account_dn"]
        group_dn = task["group_dn"]
        account_sid = task.get("account_sid", account_dn)

        if self.bh_guard:
            risk = await self.bh_guard.check_group_membership_risk(account_sid, group_dn)
            if risk["risk_level"] >= 4:
                return AgentResult(
                    task_id=task["task_id"],
                    agent_id=self.agent_id,
                    success=False,
                    output={"blocked": True, "reason": risk["reason"], "risk_level": risk["risk_level"]},
                    reasoning=f"BloodHound detected path to Tier 0 via group {group_dn}. Reason: {risk['reason']}",
                    actions_taken=[],
                    requires_approval=risk["risk_level"] == 4,
                    approval_payload={
                        "action": "add_to_group",
                        "account_dn": account_dn,
                        "group_dn": group_dn,
                        "risk_level": risk["risk_level"],
                        "path": risk.get("path"),
                    }
                    if risk["risk_level"] == 4
                    else None,
                    duration_ms=0,
                    tokens_used=0,
                )

        success = False
        if self.ldap and self.ldap._conn:
            self.ldap._conn.modify(group_dn, {"member": [("MODIFY_ADD", [account_dn])]})
            success = self.ldap._conn.result["result"] == 0

        verified = False
        verification_payload = None
        if success and self.verifier:
            check = await self.verifier.verify_group_membership(account_dn, group_dn, should_be_member=True)
            verified = check.is_consistent
            verification_payload = {
                "is_consistent": check.is_consistent,
                "inconsistencies": check.inconsistencies,
                "replication_lag_estimate_s": check.replication_lag_estimate_s,
            }

        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=success,
            output={"account_dn": account_dn, "group_dn": group_dn, "verified": verified, "verification": verification_payload},
            reasoning=f"Added {account_dn} to {group_dn}. Verification: {'OK' if verified else 'PENDING'}",
            actions_taken=[
                {
                    "action": "add_to_group",
                    "account_dn": account_dn,
                    "group_dn": group_dn,
                    "success": success,
                    "verified": verified,
                }
            ],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.BETA.value,
        )

    async def _create_service_account(self, task: dict) -> AgentResult:
        spn = task.get("spn", "")
        account = task["account_name"]
        password = task["password"]
        domain = task["domain"]

        if len(password) < 25:
            return self._error_result(
                task,
                f"Password too short ({len(password)} chars). Service accounts require >= 25 chars.",
            )

        if spn:
            krb_check = self.krb_val.check_spn_kerberoastable(account, spn, domain)
            if krb_check["is_kerberoastable"] and krb_check.get("encryption_type") == 23:
                return self._error_result(
                    task,
                    f"SPN {spn} would be RC4-kerberoastable. Configure AES-only encryption before creation.",
                )

        delegation_risks = []
        if self.ldap:
            delegation_risks = self.krb_val.check_delegation_risks(task.get("account_dn", ""), self.ldap)

        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output={
                "account": account,
                "spn": spn,
                "kerberos_validated": True,
                "delegation_risks": delegation_risks,
            },
            reasoning=f"Service account {account} validated for strong Kerberos settings",
            actions_taken=[{"action": "create_service_account", "account": account}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.BETA.value,
        )

    async def _run_drift_scan(self, task: dict) -> AgentResult:
        if not self.drift_det:
            return self._error_result(task, "DriftDetector not initialized")
        domain_dn = task["domain_dn"]
        snap = self.drift_det.take_snapshot(domain_dn)
        drifts = []
        drifts.extend(self.drift_det.detect_stale_accounts(domain_dn))
        drifts.extend(self.drift_det.detect_orphan_objects(domain_dn))

        baseline = task.get("baseline")
        if baseline:
            baseline_snap = ADSnapshot(**json.loads(baseline))
            drifts.extend(self.drift_det.detect_sensitive_group_changes(domain_dn, baseline_snap))

        expected_policies = task.get("expected_policies", {})
        if expected_policies:
            drifts.extend(self.drift_det.detect_gpo_drift(domain_dn, expected_policies))

        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=True,
            output={
                "drifts_found": len(drifts),
                "critical_count": sum(1 for drift in drifts if drift.severity >= 4),
                "drifts": [
                    {
                        "type": drift.drift_type,
                        "dn": drift.object_dn,
                        "severity": drift.severity,
                        "description": drift.description,
                        "auto_fixable": drift.auto_fixable,
                    }
                    for drift in drifts[:20]
                ],
                "snapshot_id": snap.snapshot_id,
            },
            reasoning=(
                f"Drift scan complete: {len(drifts)} drifts found, "
                f"{sum(1 for drift in drifts if drift.severity >= 4)} critical."
            ),
            actions_taken=[{"action": "drift_scan", "domain": domain_dn}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.BETA.value,
        )

    async def _restore_deleted(self, task: dict) -> AgentResult:
        object_dn = task["object_dn"]
        parent_dn = task.get("parent_dn")

        if not self.ldap or not self.ldap._conn:
            return self._error_result(task, "LDAP not initialized")

        search_base = object_dn.split(",", 1)[1] if "," in object_dn else object_dn
        deleted_objects = self.ldap.get_deleted_objects(search_base)
        match = [obj for obj in deleted_objects if object_dn.lower() in json.dumps(obj).lower()]
        if not match:
            return self._error_result(task, f"Object {object_dn} not found in AD Recycle Bin")

        success = False
        if parent_dn:
            self.ldap._conn.modify(
                object_dn,
                {
                    "isDeleted": [("MODIFY_DELETE", [])],
                    "distinguishedName": [("MODIFY_REPLACE", [object_dn])],
                },
            )
            success = self.ldap._conn.result["result"] == 0

        return AgentResult(
            task_id=task["task_id"],
            agent_id=self.agent_id,
            success=success,
            output={"restored_dn": object_dn, "success": success},
            reasoning=f"Restored {object_dn} from AD Recycle Bin",
            actions_taken=[{"action": "restore_deleted", "object_dn": object_dn}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _get_attack_path(self, task: dict) -> AgentResult:
        if not self.bh_guard:
            return self._error_result(task, "BloodHound guard not initialized")
        source = task["source"]
        target = task["target"]
        summary = await self.bh_guard.get_privilege_path_summary(source, target)
        return AgentResult(
            task_id=task.get("task_id", "attack-path"),
            agent_id=self.agent_id,
            success=True,
            output=summary,
            reasoning=f"Privilege path analysis completed for {source} -> {target}",
            actions_taken=[{"action": "get_attack_path", "source": source, "target": target}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _get_blast_radius(self, task: dict) -> AgentResult:
        if not self.bh_guard:
            return self._error_result(task, "BloodHound guard not initialized")
        entity_id = task["entity_id"]
        blast = await self.bh_guard.get_blast_radius(entity_id)
        return AgentResult(
            task_id=task.get("task_id", "blast-radius"),
            agent_id=self.agent_id,
            success=True,
            output=blast,
            reasoning=f"Blast radius computed for {entity_id}",
            actions_taken=[{"action": "get_blast_radius", "entity_id": entity_id}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _get_tier0_assets(self, task: dict) -> AgentResult:
        if not self.bh_guard:
            return self._error_result(task, "BloodHound guard not initialized")
        assets = await self.bh_guard.get_tier0_assets()
        return AgentResult(
            task_id=task.get("task_id", "tier0-assets"),
            agent_id=self.agent_id,
            success=True,
            output={"tier0_assets": assets, "count": len(assets)},
            reasoning=f"Retrieved {len(assets)} tier 0 assets",
            actions_taken=[{"action": "get_tier0_assets"}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _answer_privilege_question(self, task: dict) -> AgentResult:
        if not self.bh_guard:
            return self._error_result(task, "BloodHound guard not initialized")
        subject = task["subject"]
        question = task["question"]
        answer = await self.bh_guard.answer_privilege_question(subject, question, task.get("target"))
        return AgentResult(
            task_id=task.get("task_id", "privilege-question"),
            agent_id=self.agent_id,
            success=True,
            output=answer,
            reasoning=f"Answered privilege question for {subject}",
            actions_taken=[{"action": "answer_privilege_question", "subject": subject}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _visualize_exposure(self, task: dict) -> AgentResult:
        if not self.bh_guard:
            return self._error_result(task, "BloodHound guard not initialized")
        object_id = task["object_id"]
        exposure = await self.bh_guard.get_resource_exposure(object_id)
        return AgentResult(
            task_id=task.get("task_id", "visualize-exposure"),
            agent_id=self.agent_id,
            success=True,
            output=exposure,
            reasoning=f"Exposure visualization data prepared for {object_id}",
            actions_taken=[{"action": "visualize_exposure", "object_id": object_id}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _validate_group_membership(self, task: dict) -> AgentResult:
        if not self.bh_guard:
            return self._error_result(task, "BloodHound guard not initialized")
        account_sid = task.get("account_sid") or task.get("account_dn", "")
        group_dn = task["group_dn"]
        risk = await self.bh_guard.check_group_membership_risk(account_sid, group_dn)
        return AgentResult(
            task_id=task.get("task_id", "validate-group-membership"),
            agent_id=self.agent_id,
            success=True,
            output=risk,
            reasoning=f"Validated group membership risk for {group_dn}",
            actions_taken=[{"action": "validate_group_membership", "group_dn": group_dn}],
            requires_approval=risk.get("risk_level", 0) >= 4,
            approval_payload=risk if risk.get("risk_level", 0) >= 4 else None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _validate_service_account(self, task: dict) -> AgentResult:
        spn = task.get("spn", "")
        account = task.get("account_name") or task.get("username") or ""
        domain = task.get("domain") or os.getenv("AD_DOMAIN", "")
        result = self.krb_val.check_spn_kerberoastable(account, spn, domain) if spn else {
            "spn": spn,
            "is_kerberoastable": False,
            "encryption_type": None,
            "risk_level": 0,
        }
        delegation_risks = self.krb_val.check_delegation_risks(task.get("account_dn", ""), self.ldap) if self.ldap else []
        output = {
            **result,
            "delegation_risks": delegation_risks,
            "password_length": len(str(task.get("password", ""))),
            "password_policy_ok": len(str(task.get("password", ""))) >= 25 if task.get("password") is not None else None,
        }
        return AgentResult(
            task_id=task.get("task_id", "validate-service-account"),
            agent_id=self.agent_id,
            success=True,
            output=output,
            reasoning=f"Validated service account posture for {account or spn}",
            actions_taken=[{"action": "validate_service_account", "spn": spn}],
            requires_approval=output.get("risk_level", 0) >= 4,
            approval_payload=output if output.get("risk_level", 0) >= 4 else None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _get_object_acl(self, task: dict) -> AgentResult:
        if not self.ldap:
            return self._error_result(task, "LDAP not initialized")
        dn = task["dn"]
        acl = self.ldap.get_object_acl(dn)
        return AgentResult(
            task_id=task.get("task_id", "get-object-acl"),
            agent_id=self.agent_id,
            success=acl is not None,
            output={"dn": dn, "acl": acl},
            reasoning=f"Read ACL for {dn}",
            actions_taken=[{"action": "get_object_acl", "dn": dn}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _get_deleted_objects(self, task: dict) -> AgentResult:
        if not self.ldap:
            return self._error_result(task, "LDAP not initialized")
        base_dn = task["base_dn"]
        deleted = self.ldap.get_deleted_objects(base_dn)
        return AgentResult(
            task_id=task.get("task_id", "get-deleted-objects"),
            agent_id=self.agent_id,
            success=True,
            output={"base_dn": base_dn, "count": len(deleted), "objects": deleted[:50]},
            reasoning=f"Retrieved {len(deleted)} deleted AD objects",
            actions_taken=[{"action": "get_deleted_objects", "base_dn": base_dn}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    async def _dirsync_changes(self, task: dict) -> AgentResult:
        if not self.ldap:
            return self._error_result(task, "LDAP not initialized")
        base_dn = task["base_dn"]
        cookie = task.get("last_cookie")
        if isinstance(cookie, str):
            cookie = cookie.encode()
        changes, new_cookie = self.ldap.dirsync_changes(base_dn, cookie)
        return AgentResult(
            task_id=task.get("task_id", "dirsync-changes"),
            agent_id=self.agent_id,
            success=True,
            output={"base_dn": base_dn, "count": len(changes), "changes": changes[:50], "cookie": new_cookie.decode(errors="ignore")},
            reasoning=f"Retrieved {len(changes)} incremental changes from AD",
            actions_taken=[{"action": "dirsync_changes", "base_dn": base_dn}],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.EXECUTE.value,
            capability_maturity=CapabilityMaturity.PREPROD_READY.value,
        )

    def _error_result(self, task: dict, reason: str) -> AgentResult:
        return AgentResult(
            task_id=task.get("task_id", "unknown"),
            agent_id=self.agent_id,
            success=False,
            output={"error": reason},
            reasoning=reason,
            actions_taken=[],
            requires_approval=False,
            approval_payload=None,
            duration_ms=0,
            tokens_used=0,
            execution_mode=ExecutionMode.PREPARE.value,
            capability_maturity=CapabilityMaturity.STUBBED.value,
        )
