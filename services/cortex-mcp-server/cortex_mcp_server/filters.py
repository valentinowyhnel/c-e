from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class FilterResult:
    passed: bool
    blocked: bool
    reason: str
    modified: bool
    cleaned: Any | None


class InputFilter:
    INJECTION_PATTERNS = [
        r"ignore\s+(all\s+)?previous\s+instructions",
        r"forget\s+(all\s+)?previous",
        r"developer\s+mode",
        r"jailbreak",
        r"__import__",
        r"subprocess",
        r"os\.system",
    ]

    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z|a-z]{2,}\b",
        "ipv4": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }

    def __init__(self, max_input_size: int = 50_000, strict: bool = True, redact_pii: bool = True):
        self.max_input_size = max_input_size
        self.strict = strict
        self.redact_pii = redact_pii

    def filter(self, input_text: str, context: dict[str, object]) -> FilterResult:
        if len(input_text) > self.max_input_size:
            return FilterResult(False, True, "input_too_large", False, None)

        if self.strict:
            for pattern in self.INJECTION_PATTERNS:
                if re.search(pattern, input_text, re.IGNORECASE | re.DOTALL):
                    return FilterResult(False, True, "prompt_injection_detected", False, None)

        if context.get("expect_json"):
            try:
                json.loads(input_text)
            except Exception:
                return FilterResult(False, True, "invalid_json_when_expected", False, None)

        cleaned = input_text
        modified = False
        if self.redact_pii:
            for pii_type, pattern in self.PII_PATTERNS.items():
                cleaned, count = re.subn(pattern, f"[REDACTED_{pii_type.upper()}]", cleaned)
                modified = modified or count > 0

        if "../" in input_text or "..\\" in input_text:
            return FilterResult(False, True, "path_traversal_detected", False, None)

        return FilterResult(True, False, "all_filters_passed", modified, cleaned if modified else None)


class OutputFilter:
    SECRET_PATTERNS = [
        r"AKIA[0-9A-Z]{16}",
        r"sk-[A-Za-z0-9]{20,}",
        r"sk-ant-[a-zA-Z0-9\-_]{20,}",
        r"hvs\.[A-Za-z0-9._-]{20,}",
        r"-----BEGIN\s+OPENSSH\s+PRIVATE KEY-----",
        r"-----BEGIN\s+(RSA\s+)?PRIVATE KEY-----",
    ]

    def __init__(self, max_output_size: int = 100_000):
        self.max_output_size = max_output_size

    def filter(self, output: str, expected_format: str = "text", strip_markdown: bool = False) -> FilterResult:
        text = output
        modified = False

        if len(text) > self.max_output_size:
            text = text[: self.max_output_size] + "\n[OUTPUT_TRUNCATED]"
            modified = True

        for pattern in self.SECRET_PATTERNS:
            if re.search(pattern, text):
                return FilterResult(False, True, "secret_pattern_in_output", False, None)

        if expected_format == "json":
            extracted = self._extract_json(text)
            if extracted is None:
                return FilterResult(False, True, "expected_json_but_invalid", False, None)
            return FilterResult(True, False, "json_extracted", True, extracted)

        if expected_format == "code" or strip_markdown:
            cleaned = self._strip_markdown_code_blocks(text)
            return FilterResult(True, False, "markdown_stripped", True, cleaned)

        return FilterResult(True, False, "output_clean", modified, text if modified else None)

    def _extract_json(self, text: str) -> str | None:
        try:
            json.loads(text)
            return text
        except Exception:
            pass

        match = re.search(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", text, re.DOTALL)
        if match:
            candidate = match.group(1)
            try:
                json.loads(candidate)
                return candidate
            except Exception:
                return None
        return None

    def _strip_markdown_code_blocks(self, text: str) -> str:
        text = re.sub(r"^```\w*\n?", "", text, flags=re.MULTILINE)
        text = re.sub(r"\n?```$", "", text, flags=re.MULTILINE)
        return text.strip()
