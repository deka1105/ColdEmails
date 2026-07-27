"""Lightweight, no-cost email validation — the *safe* half of an SMTP verifier.

Two checks only, both cheap and non-abusive:

1. **Syntax** — RFC-ish shape check via regex.
2. **MX** — does the domain publish mail servers? (one DNS lookup, cached).

Deliberately *not* implemented: the SMTP ``RCPT TO`` handshake. Probing a mail
server to confirm a specific mailbox is unreliable on the big providers (Gmail /
Microsoft accept everything or greylist) and doing it from the same box you send
from is exactly what spam filters watch for — a bad trade for a deliverability
tool. So we stop at "the domain can receive mail", which is genuinely useful for
dropping typo'd / dead domains before spending a draft on them.

Offline-safe: with ``COLDEMAILS_NO_NETWORK_RESOLVE=1`` (set in tests) or when
``dnspython`` is absent, ``has_mx`` returns ``None`` ("unknown") instead of
touching the network. Callers treat ``None`` as "keep going".
"""

from __future__ import annotations

import re

from .config import env

# Pragmatic address shape: local@domain.tld. Not full RFC 5322 — just enough to
# reject the obviously-broken before a DNS call or a draft.
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@([A-Za-z0-9](?:[A-Za-z0-9\-]*[A-Za-z0-9])?\.)+[A-Za-z]{2,}$"
)

_mx_cache: dict[str, bool | None] = {}


def valid_syntax(email: str | None) -> bool:
    """True if ``email`` has a plausible address shape."""
    if not email:
        return False
    return bool(_EMAIL_RE.match(email.strip()))


def has_mx(domain: str) -> bool | None:
    """Does ``domain`` publish MX (or fallback A) records for mail?

    Returns ``True``/``False`` when it can tell, or ``None`` when it can't
    (network disabled, ``dnspython`` missing, or lookup error) — never raises.
    """
    domain = (domain or "").strip().lower()
    if not domain:
        return False
    if domain in _mx_cache:
        return _mx_cache[domain]
    if env("COLDEMAILS_NO_NETWORK_RESOLVE"):
        return None

    result: bool | None
    try:
        import dns.resolver  # type: ignore

        try:
            answers = dns.resolver.resolve(domain, "MX")
            result = len(answers) > 0
        except (dns.resolver.NoAnswer, dns.resolver.NXDOMAIN):
            # RFC 5321: no MX means fall back to the domain's A record.
            try:
                dns.resolver.resolve(domain, "A")
                result = True
            except Exception:
                result = False
    except ImportError:
        result = None  # dnspython not installed — treat as unknown, don't block.
    except Exception:
        result = None  # timeout / transient DNS error — unknown, don't block.

    _mx_cache[domain] = result
    return result


def validate(email: str | None, *, check_mx: bool = True) -> dict:
    """Validate ``email`` and return a small report.

    Keys: ``email``, ``syntax`` (bool), ``mx`` (bool|None), ``deliverable``
    (bool|None — False only when a check actively fails), ``confidence`` (0-100).
    """
    syntax = valid_syntax(email)
    domain = email.split("@", 1)[1] if syntax and email else ""
    mx: bool | None = has_mx(domain) if (syntax and check_mx) else None

    if not syntax:
        deliverable: bool | None = False
        confidence = 0
    elif mx is False:
        deliverable = False
        confidence = 10
    elif mx is True:
        deliverable = True
        confidence = 70  # domain accepts mail; mailbox itself unverified.
    else:  # mx unknown
        deliverable = None
        confidence = 50

    return {
        "email": email,
        "syntax": syntax,
        "mx": mx,
        "deliverable": deliverable,
        "confidence": confidence,
    }
