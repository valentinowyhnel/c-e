from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any


@dataclass
class ActionVerificationResult:
    action_type: str
    target_dn: str
    expected_state: dict[str, Any]
    actual_state: dict[str, Any]
    is_consistent: bool
    inconsistencies: list[str]
    replication_lag_estimate_s: float


class ADActionVerifier:
    RETRY_INTERVALS = [2, 5, 15, 30]

    def __init__(self, ldap):
        self.ldap = ldap

    async def verify_user_created(self, dn: str, expected_attrs: dict[str, Any]) -> ActionVerificationResult:
        for wait_s in self.RETRY_INTERVALS:
            await asyncio.sleep(wait_s)
            results = self.ldap.search_paged(dn, "(objectClass=user)", list(expected_attrs.keys()))
            if not results:
                continue
            actual = results[0]
            inconsistencies = [
                f"{attr}: expected={expected_attrs[attr]}, got={actual.get(attr)}"
                for attr in expected_attrs
                if actual.get(attr) != expected_attrs[attr]
            ]
            return ActionVerificationResult(
                action_type="create_user",
                target_dn=dn,
                expected_state=expected_attrs,
                actual_state=actual,
                is_consistent=len(inconsistencies) == 0,
                inconsistencies=inconsistencies,
                replication_lag_estimate_s=wait_s,
            )
        return ActionVerificationResult(
            action_type="create_user",
            target_dn=dn,
            expected_state=expected_attrs,
            actual_state={},
            is_consistent=False,
            inconsistencies=["object_not_found_after_creation"],
            replication_lag_estimate_s=sum(self.RETRY_INTERVALS),
        )

    async def verify_group_membership(
        self,
        account_dn: str,
        group_dn: str,
        should_be_member: bool = True,
    ) -> ActionVerificationResult:
        for wait_s in self.RETRY_INTERVALS:
            await asyncio.sleep(wait_s)
            results = self.ldap.search_paged(account_dn, "(objectClass=*)", ["memberOf"])
            if not results:
                continue
            member_of = results[0].get("memberOf", [])
            if not isinstance(member_of, list):
                member_of = [member_of]
            normalized = [group.lower() for group in member_of]
            is_member = group_dn.lower() in normalized
            consistent = is_member == should_be_member
            return ActionVerificationResult(
                action_type="group_membership",
                target_dn=account_dn,
                expected_state={"member_of": group_dn, "should_be_member": should_be_member},
                actual_state={"is_member": is_member, "all_groups": member_of},
                is_consistent=consistent,
                inconsistencies=[] if consistent else [f"expected is_member={should_be_member}, got {is_member}"],
                replication_lag_estimate_s=wait_s,
            )
        return ActionVerificationResult(
            action_type="group_membership",
            target_dn=account_dn,
            expected_state={},
            actual_state={},
            is_consistent=False,
            inconsistencies=["verification_timeout"],
            replication_lag_estimate_s=sum(self.RETRY_INTERVALS),
        )
