"""Shared utilities for agentlint check modules."""

from __future__ import annotations

import re

# Exactly 3 backticks at start of line — opening/closing a code fence.
_CODE_FENCE_RE = re.compile(r"^```(?!`)")
