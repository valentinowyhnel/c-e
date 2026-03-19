from __future__ import annotations


class CriticalActionGuard:
    def authorize(self, *, cortex_token: str | None, approved: bool) -> bool:
        return bool(cortex_token) and approved

