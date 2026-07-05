"""Turn a prospect + campaign into a ready-to-send Message.

Two renderers behind one interface:
- TemplateRenderer: fills the campaign prompt string with fields (no LLM, free,
  deterministic) — handy for testing without an API key.
- ClaudeRenderer: uses the campaign prompt as an instruction to Claude to write
  the email body; subject falls back to the campaign's ``fallback_subject``.
"""

from __future__ import annotations

import shutil
import subprocess
from abc import ABC, abstractmethod
from typing import Any

from .config import env
from .models import Criteria, Message, Person

# Latest small, fast Claude model for short outreach copy.
CLAUDE_MODEL = "claude-haiku-4-5-20251001"


def _fields(person: Person, criteria: Criteria, campaign: dict[str, Any]) -> dict[str, str]:
    return {
        "name": person.name or "there",
        "title": person.title or "",
        "company": person.company or criteria.company or "",
        "domain": person.domain or criteria.domain or "",
        # The prospect's own org (e.g. the VC firm) vs. the input/startup domain.
        "firm": person.company or "",
        "startup_domain": criteria.domain or "",
        "role": criteria.role or "",
        "location": criteria.location or "",
        "background": person.background or "",
    }


def _fill(text: str, fields: dict[str, str]) -> str:
    class _Safe(dict):
        def __missing__(self, k: str) -> str:  # leave unknown {placeholders} intact
            return ""

    return text.format_map(_Safe(fields))


_OUTPUT_INSTRUCTIONS = (
    "\n\nOutput format: first line exactly 'Subject: <a specific subject under "
    "60 chars>', then a blank line, then the email body only — no preamble, no "
    "signature placeholder brackets."
)


def _parse_email(text: str, fallback_subject: str) -> Message:
    """Split model output into (subject, body); tolerate a missing subject line."""
    text = text.strip()
    lines = text.splitlines()
    if lines and lines[0].lower().startswith("subject:"):
        subject = lines[0].split(":", 1)[1].strip() or fallback_subject
        body = "\n".join(lines[1:]).strip()
        if body:
            return Message(subject=subject, body=body)
    return Message(subject=fallback_subject, body=text)


class Personalizer(ABC):
    name: str = "base"

    @abstractmethod
    def render(self, person: Person, criteria: Criteria, campaign: dict[str, Any]) -> Message:
        ...


class TemplateRenderer(Personalizer):
    name = "template"

    def render(self, person: Person, criteria: Criteria, campaign: dict[str, Any]) -> Message:
        fields = _fields(person, criteria, campaign)
        subject = _fill(campaign.get("fallback_subject", "Hello"), fields)
        body = _fill(campaign.get("prompt", ""), fields)
        return Message(subject=subject, body=body)


class ClaudeRenderer(Personalizer):
    name = "claude"

    def __init__(self) -> None:
        # Imported lazily so the package works without the SDK for template runs.
        from anthropic import Anthropic

        self.client = Anthropic(api_key=env("ANTHROPIC_API_KEY", required=True))

    def render(self, person: Person, criteria: Criteria, campaign: dict[str, Any]) -> Message:
        fields = _fields(person, criteria, campaign)
        instruction = _fill(campaign.get("prompt", ""), fields)
        prompt = instruction + _OUTPUT_INSTRUCTIONS
        resp = self.client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(block.text for block in resp.content if block.type == "text")
        fallback = _fill(campaign.get("fallback_subject", "Hello"), fields)
        return _parse_email(text, fallback)


class ClaudeCLIRenderer(Personalizer):
    """Generate copy via the local Claude Code CLI (``claude -p``).

    Uses the machine's existing Claude Code login instead of an API key — handy
    when running from Claude Code / a logged-in dev machine. Requires the
    ``claude`` binary on PATH.
    """

    name = "claude_cli"

    def __init__(self) -> None:
        self.bin = shutil.which("claude")
        if not self.bin:
            raise RuntimeError(
                "Claude Code CLI ('claude') not found on PATH. Install it or use "
                "the 'claude' (API key) or 'template' personalizer instead."
            )

    def render(self, person: Person, criteria: Criteria, campaign: dict[str, Any]) -> Message:
        fields = _fields(person, criteria, campaign)
        instruction = _fill(campaign.get("prompt", ""), fields)
        prompt = instruction + _OUTPUT_INSTRUCTIONS
        # The CLI otherwise inherits the caller's session model, which may be
        # unavailable; pin an explicit, valid model (override via env).
        model = env("COLDEMAILS_CLAUDE_CLI_MODEL") or CLAUDE_MODEL
        try:
            proc = subprocess.run(
                [self.bin, "-p", "--model", model, prompt],
                capture_output=True,
                text=True,
                timeout=120,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError("claude CLI timed out") from e
        if proc.returncode != 0:
            raise RuntimeError(f"claude CLI failed: {proc.stderr.strip()[:200]}")
        fallback = _fill(campaign.get("fallback_subject", "Hello"), fields)
        return _parse_email(proc.stdout, fallback)


_RENDERERS: dict[str, type[Personalizer]] = {
    "template": TemplateRenderer,
    "claude": ClaudeRenderer,
    "claude_cli": ClaudeCLIRenderer,
}


def get_personalizer(name: str) -> Personalizer:
    if name not in _RENDERERS:
        raise ValueError(
            f"Unknown personalizer '{name}'. Available: {', '.join(_RENDERERS)}"
        )
    return _RENDERERS[name]()
