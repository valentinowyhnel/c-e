from __future__ import annotations

from typing import Any

try:
    from impacket.krb5 import constants
    from impacket.krb5.kerberosv5 import getKerberosTGS
    from impacket.krb5.types import Principal
except ImportError:  # pragma: no cover - optional dependency at runtime
    constants = None
    getKerberosTGS = None
    Principal = None

from ..logging import get_logger

log = get_logger(__name__)


class KerberosValidator:
    """
    Validation Kerberos défensive avant les changements sensibles AD.
    """

    def check_spn_kerberoastable(self, username: str, spn: str, domain: str) -> dict[str, Any]:
        result = {
            "username": username,
            "spn": spn,
            "is_kerberoastable": False,
            "encryption_type": None,
            "risk_level": 0,
        }
        if not spn or getKerberosTGS is None or Principal is None or constants is None:
            return result
        try:
            tgs, _, _, _ = getKerberosTGS(
                Principal(spn, type=constants.PrincipalNameType.NT_SRV_INST.value),
                domain,
                None,
            )
            enc_type = tgs["ticket"]["enc-part"]["etype"]
            result["is_kerberoastable"] = True
            result["encryption_type"] = enc_type
            result["risk_level"] = 5 if enc_type == 23 else 2 if enc_type == 18 else 3
            if enc_type == 23:
                log.warning("kerberos.spn.rc4_kerberoastable", spn=spn)
            return result
        except Exception as exc:
            log.info("kerberos.spn.check_failed", spn=spn, error=str(exc)[:200])
            return result

    def check_delegation_risks(self, account_dn: str, ldap: Any) -> list[str]:
        risks: list[str] = []
        attrs = ldap.search_paged(
            base_dn=account_dn,
            filter_str="(objectClass=*)",
            attributes=[
                "userAccountControl",
                "msDS-AllowedToDelegateTo",
                "msDS-AllowedToActOnBehalfOfOtherIdentity",
            ],
        )
        for obj in attrs:
            uac = int(obj.get("userAccountControl", 0) or 0)
            if uac & 0x80000:
                risks.append("unconstrained_delegation")
            if obj.get("msDS-AllowedToDelegateTo"):
                risks.append("constrained_delegation_configured")
            if obj.get("msDS-AllowedToActOnBehalfOfOtherIdentity"):
                risks.append("rbcd_configured")
        return sorted(set(risks))
