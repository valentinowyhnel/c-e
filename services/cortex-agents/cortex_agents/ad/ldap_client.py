from __future__ import annotations

from typing import Any

try:
    from ldap3 import ALL, BASE, NTLM, SASL, SUBTREE, Connection, Server
    from ldap3.protocol.microsoft import dir_sync_control, security_descriptor_control, show_deleted_control
except ImportError:  # pragma: no cover - optional dependency at runtime
    ALL = BASE = NTLM = SASL = SUBTREE = None
    Connection = Server = None
    dir_sync_control = security_descriptor_control = show_deleted_control = None

from ..logging import get_logger

log = get_logger(__name__)


class CortexLDAPClient:
    """
    Client LDAP enrichi pour les opérations AD Cortex.
    """

    def __init__(
        self,
        dc_host: str,
        domain: str,
        username: str,
        password: str,
        use_ssl: bool = True,
        page_size: int = 500,
    ):
        self.domain = domain
        self.page_size = page_size
        self._bind_user = f"{username}@{domain}"
        self._bind_password = password
        self._conn: Any | None = None
        self._server = None
        if Server is not None:
            self._server = Server(
                dc_host,
                port=636 if use_ssl else 389,
                use_ssl=use_ssl,
                get_info=ALL,
                connect_timeout=5,
            )

    @property
    def is_connected(self) -> bool:
        return self._conn is not None

    def connect(self) -> bool:
        if Connection is None or self._server is None:
            log.error("ldap.connect.unavailable")
            return False
        try:
            self._conn = Connection(
                self._server,
                user=self._bind_user,
                password=self._bind_password,
                authentication=SASL,
                sasl_mechanism="GSSAPI",
                auto_bind=True,
                receive_timeout=30,
                auto_encode=True,
                auto_decode=True,
                auto_referrals=False,
            )
            log.info("ldap.connected", dc=self._server.host)
            return True
        except Exception as exc:
            log.error("ldap.connect.error", error=str(exc))
        try:
            self._conn = Connection(
                self._server,
                user=self._bind_user,
                password=self._bind_password,
                authentication=NTLM,
                auto_bind=True,
            )
            log.warning("ldap.connected.ntlm_fallback", dc=self._server.host)
            return True
        except Exception as exc:
            log.error("ldap.connect.ntlm.error", error=str(exc))
            return False

    def search_paged(self, base_dn: str, filter_str: str, attributes: list[str]) -> list[dict[str, Any]]:
        if not self._conn:
            return []
        results: list[dict[str, Any]] = []
        cookie = None
        while True:
            self._conn.search(
                search_base=base_dn,
                search_filter=filter_str,
                search_scope=SUBTREE,
                attributes=attributes,
                paged_size=self.page_size,
                paged_cookie=cookie,
            )
            results.extend(
                [
                    {attr: entry[attr].value for attr in attributes if attr in entry}
                    for entry in self._conn.entries
                ]
            )
            cookie = (
                self._conn.result.get("controls", {})
                .get("1.2.840.113556.1.4.319", {})
                .get("value", {})
                .get("cookie")
            )
            if not cookie:
                break
        return results

    def get_deleted_objects(self, base_dn: str) -> list[dict[str, Any]]:
        if not self._conn or show_deleted_control is None:
            return []
        self._conn.search(
            search_base=base_dn,
            search_filter="(isDeleted=TRUE)",
            search_scope=SUBTREE,
            attributes=["cn", "distinguishedName", "objectClass", "whenChanged", "lastKnownParent"],
            controls=show_deleted_control(),
        )
        return [entry.entry_attributes_as_dict for entry in self._conn.entries]

    def get_object_acl(self, dn: str) -> dict[str, Any] | None:
        if not self._conn or security_descriptor_control is None:
            return None
        self._conn.search(
            search_base=dn,
            search_filter="(objectClass=*)",
            search_scope=BASE,
            attributes=["nTSecurityDescriptor"],
            controls=security_descriptor_control(sdflags=0x04),
        )
        if self._conn.entries:
            return self._conn.entries[0].entry_attributes_as_dict
        return None

    def dirsync_changes(self, base_dn: str, last_cookie: bytes | None = None) -> tuple[list[dict[str, Any]], bytes]:
        if not self._conn or dir_sync_control is None:
            return [], b""
        ctrl = dir_sync_control(
            is_critical=True,
            parent_first=True,
            object_security=False,
            ancestors_first=False,
            public_data_only=False,
            incremental_values=True,
            max_length=2147483647,
            cookie=last_cookie or b"",
        )
        self._conn.search(
            search_base=base_dn,
            search_filter="(objectClass=*)",
            search_scope=SUBTREE,
            attributes=["*"],
            controls=[ctrl],
        )
        changes = [entry.entry_attributes_as_dict for entry in self._conn.entries]
        new_cookie = (
            self._conn.result.get("controls", {})
            .get("1.2.840.113556.1.4.841", {})
            .get("value", {})
            .get("cookie", b"")
        )
        return changes, new_cookie
