from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any

from ..logging import get_logger

log = get_logger(__name__)


@dataclass
class ADDrift:
    drift_id: str
    drift_type: str
    object_dn: str
    description: str
    severity: int
    detected_at: float
    expected: Any
    actual: Any
    auto_fixable: bool = False
    fix_action: str | None = None
    ttl_days: int = 7


@dataclass
class ADSnapshot:
    snapshot_id: str
    taken_at: float
    domain: str
    user_count: int
    group_count: int
    computer_count: int
    object_hashes: dict[str, str] = field(default_factory=dict)
    sensitive_group_members: dict[str, list[str]] = field(default_factory=dict)


class ADDriftDetector:
    STALE_USER_DAYS = 90
    STALE_COMPUTER_DAYS = 60
    MAX_PASSWORD_AGE_DAYS = 365
    MAX_GROUP_MEMBERS = 5000
    SENSITIVE_GROUPS = [
        "Domain Admins",
        "Enterprise Admins",
        "Schema Admins",
        "Backup Operators",
        "Account Operators",
        "Server Operators",
        "Group Policy Creator Owners",
    ]

    def __init__(self, ldap, neo4j_client=None):
        self.ldap = ldap
        self.neo4j = neo4j_client
        self._baseline: ADSnapshot | None = None

    def take_snapshot(self, domain_dn: str) -> ADSnapshot:
        snap = ADSnapshot(
            snapshot_id=hashlib.sha256(f"{domain_dn}{time.time()}".encode()).hexdigest()[:16],
            taken_at=time.time(),
            domain=domain_dn,
            user_count=0,
            group_count=0,
            computer_count=0,
        )
        users = self.ldap.search_paged(domain_dn, "(objectClass=user)", ["distinguishedName", "whenChanged"])
        groups = self.ldap.search_paged(domain_dn, "(objectClass=group)", ["distinguishedName", "whenChanged"])
        computers = self.ldap.search_paged(domain_dn, "(objectClass=computer)", ["distinguishedName", "whenChanged"])
        snap.user_count = len(users)
        snap.group_count = len(groups)
        snap.computer_count = len(computers)
        for obj in [*users, *groups, *computers]:
            dn = obj.get("distinguishedName", "")
            when = str(obj.get("whenChanged", ""))
            if dn:
                snap.object_hashes[dn] = hashlib.md5(when.encode()).hexdigest()
        for group_name in self.SENSITIVE_GROUPS:
            members = self.ldap.search_paged(domain_dn, f"(&(objectClass=group)(cn={group_name}))", ["member"])
            if not members:
                continue
            member_list = members[0].get("member", [])
            if not isinstance(member_list, list):
                member_list = [member_list] if member_list else []
            snap.sensitive_group_members[group_name] = member_list
        self._baseline = snap
        log.info("ad.snapshot.taken", snap_id=snap.snapshot_id, users=snap.user_count)
        return snap

    def detect_stale_accounts(self, domain_dn: str) -> list[ADDrift]:
        drifts: list[ADDrift] = []
        cutoff_ldap = self._days_to_ldap_timestamp(self.STALE_USER_DAYS)
        stale_users = self.ldap.search_paged(
            domain_dn,
            (
                f"(&(objectClass=user)(objectCategory=person)"
                f"(!(userAccountControl:1.2.840.113556.1.4.803:=2))"
                f"(lastLogonTimestamp<={cutoff_ldap}))"
            ),
            ["distinguishedName", "cn", "lastLogonTimestamp", "userAccountControl", "memberOf"],
        )
        for user in stale_users:
            dn = user.get("distinguishedName", "")
            drifts.append(
                ADDrift(
                    drift_id=hashlib.sha256(dn.encode()).hexdigest()[:12],
                    drift_type="stale_account",
                    object_dn=dn,
                    description=(
                        f"Account not used for > {self.STALE_USER_DAYS} days. "
                        f"Last logon: {user.get('lastLogonTimestamp', 'never')}"
                    ),
                    severity=3,
                    detected_at=time.time(),
                    expected=f"lastLogon within {self.STALE_USER_DAYS} days",
                    actual=user.get("lastLogonTimestamp"),
                    auto_fixable=True,
                    fix_action="disable_account",
                    ttl_days=14,
                )
            )
        return drifts

    def detect_sensitive_group_changes(self, domain_dn: str, baseline: ADSnapshot) -> list[ADDrift]:
        drifts: list[ADDrift] = []
        for group_name in self.SENSITIVE_GROUPS:
            current = self.ldap.search_paged(domain_dn, f"(&(objectClass=group)(cn={group_name}))", ["member"])
            if not current:
                continue
            current_members = current[0].get("member", [])
            if not isinstance(current_members, list):
                current_members = [current_members] if current_members else []
            added = set(current_members) - set(baseline.sensitive_group_members.get(group_name, []))
            for dn in added:
                drifts.append(
                    ADDrift(
                        drift_id=hashlib.sha256(f"{group_name}{dn}added".encode()).hexdigest()[:12],
                        drift_type="sensitive_group_change",
                        object_dn=dn,
                        description=f"Account added to sensitive group '{group_name}' outside of Cortex workflow",
                        severity=5,
                        detected_at=time.time(),
                        expected=f"member of {group_name}: NO",
                        actual=f"member of {group_name}: YES",
                        auto_fixable=False,
                        fix_action="remove_from_sensitive_group",
                        ttl_days=1,
                    )
                )
        return drifts

    def detect_gpo_drift(self, domain_dn: str, expected_policies: dict[str, str]) -> list[ADDrift]:
        drifts: list[ADDrift] = []
        current_gpos = self.ldap.search_paged(
            domain_dn,
            "(objectClass=groupPolicyContainer)",
            ["cn", "displayName", "versionNumber", "gPCFileSysPath", "whenChanged"],
        )
        for gpo in current_gpos:
            name = gpo.get("displayName", "")
            if name not in expected_policies:
                continue
            current_hash = hashlib.md5(str(gpo.get("versionNumber", "0")).encode()).hexdigest()
            if current_hash == expected_policies[name]:
                continue
            drifts.append(
                ADDrift(
                    drift_id=hashlib.sha256(f"gpo_{name}".encode()).hexdigest()[:12],
                    drift_type="gpo_drift",
                    object_dn=gpo.get("cn", ""),
                    description=f"GPO '{name}' was modified outside Cortex workflow. Version changed: {gpo.get('versionNumber')}",
                    severity=4,
                    detected_at=time.time(),
                    expected=expected_policies[name],
                    actual=current_hash,
                    auto_fixable=False,
                    fix_action="rollback_gpo_or_validate",
                    ttl_days=3,
                )
            )
        return drifts

    def detect_orphan_objects(self, domain_dn: str) -> list[ADDrift]:
        drifts: list[ADDrift] = []
        orphans = self.ldap.search_paged(
            domain_dn,
            "(&(objectClass=user)(|(distinguishedName=*LostAndFound*)(!(manager=*))(!(department=*))))",
            ["distinguishedName", "cn", "whenCreated"],
        )
        for obj in orphans:
            dn = obj.get("distinguishedName", "")
            drifts.append(
                ADDrift(
                    drift_id=hashlib.sha256(dn.encode()).hexdigest()[:12],
                    drift_type="orphan_object",
                    object_dn=dn,
                    description=f"Object without valid parent/department/manager. Created: {obj.get('whenCreated')}",
                    severity=2,
                    detected_at=time.time(),
                    expected="object has manager and department",
                    actual="missing organizational attributes",
                    auto_fixable=True,
                    fix_action="flag_for_review_or_disable",
                    ttl_days=30,
                )
            )
        return drifts

    def _days_to_ldap_timestamp(self, days: int) -> int:
        cutoff_unix = time.time() - (days * 86400)
        return int((cutoff_unix + 11644473600) * 10000000)

    async def publish_drifts_to_cortex(self, drifts: list[ADDrift], nats_client) -> None:
        for drift in drifts:
            await nats_client.publish(
                "cortex.ad.drifts",
                json.dumps(
                    {
                        "drift_id": drift.drift_id,
                        "drift_type": drift.drift_type,
                        "object_dn": drift.object_dn,
                        "description": drift.description,
                        "severity": drift.severity,
                        "auto_fixable": drift.auto_fixable,
                        "fix_action": drift.fix_action,
                        "ttl_days": drift.ttl_days,
                        "timestamp": drift.detected_at,
                    }
                ).encode(),
            )
            if self.neo4j and drift.severity >= 3:
                await self.neo4j.execute(
                    """
                    MATCH (obj {dn: $dn})
                    MERGE (d:ADDrift {drift_id: $drift_id})
                    SET d.type = $type, d.severity = $severity, d.detected = $ts
                    MERGE (obj)-[:HAS_DRIFT]->(d)
                    """,
                    dn=drift.object_dn,
                    drift_id=drift.drift_id,
                    type=drift.drift_type,
                    severity=drift.severity,
                    ts=drift.detected_at,
                )
