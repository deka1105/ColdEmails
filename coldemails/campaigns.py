"""Campaign definitions.

A campaign is pure config: which prospect source to query, how to target
(department/seniority), whether to enrich background, and the prompt/template
used to personalize. Adding a new use case = add an entry here (plus a template).

Stored as a Python dict rather than YAML files because the package directory is
read-only in some environments; the shape mirrors what a YAML config would hold.
"""

from __future__ import annotations

from typing import Any

CAMPAIGNS: dict[str, dict[str, Any]] = {
    # Use case A — job outreach.
    # Input: company + role + location. Target hiring/HR contacts on the
    # company domain; light or no background enrichment needed.
    "jobs": {
        "source": "hunter",
        "requires": ["company", "role"],
        "targeting": {"department": "hr", "seniority": "senior,executive"},
        "enrich": None,
        "personalizer": "claude",
        "throttle_seconds": 30,
        "prompt": (
            "You are helping a job seeker write a short, genuine cold email to a "
            "hiring contact at {company}. They are interested in the role: {role} "
            "(location: {location}). Recipient: {name}, {title}. "
            "Write a concise (<140 words), specific, non-salesy email expressing "
            "interest and asking about opportunities. Honest and warm, no buzzwords."
        ),
        "fallback_subject": "Interested in {role} opportunities at {company}",
    },
    # Use case B — fundraising.
    # Input: startup domain + location. Target investors; enrich each investor's
    # background/thesis so the message references it.
    "fundraising": {
        "source": "hunter_firms",
        "requires": ["domain"],  # startup domain, used as email context
        "needs_firms": True,     # target VC/angel firm domains via --firms
        "targeting": {"seniority": "executive"},
        "enrich": "search",      # research the individual investor
        "personalizer": "claude",
        "throttle_seconds": 45,
        "prompt": (
            "You are helping a startup founder (their company domain: "
            "{startup_domain}, location: {location}) write a short cold email to an "
            "investor at {firm}. Recipient: {name}, {title}. "
            "Investor background: {background}. "
            "Write a concise (<150 words) email that references the investor's "
            "thesis/background, states what the startup does in one line, and asks "
            "for a short intro call. Specific and credible, no hype."
        ),
        "fallback_subject": "Quick intro — {startup_domain}",
    },
    # Use case C — B2B sales.
    # Input: target company (resolved to a domain) + what you're offering,
    # passed via --role. Target decision-makers (IT / management / executive).
    "b2b": {
        "source": "hunter",
        "requires": ["company", "role"],
        "targeting": {"department": "executive,it,management", "seniority": "executive,senior"},
        "enrich": None,
        "personalizer": "claude",
        "throttle_seconds": 40,
        "prompt": (
            "You are helping a salesperson write a short B2B cold email to a "
            "decision-maker at {company} (location: {location}). "
            "Recipient: {name}, {title}. What we offer: {role}. "
            "Write a concise (<130 words) email that ties the offer to a plausible "
            "pain point for their role/company and asks for a brief call. "
            "Specific and respectful, no hard-sell buzzwords."
        ),
        "fallback_subject": "{role} for {company}?",
    },
    # Use case D — PR / media.
    # Input: publication domain + story angle (via --role). Target editorial /
    # communications contacts; enrich to reference their beat/recent work.
    "pr": {
        "source": "hunter",
        "requires": ["domain", "role"],
        "targeting": {"department": "communication,marketing", "seniority": "senior,executive"},
        "enrich": "web",
        "personalizer": "claude",
        "throttle_seconds": 45,
        "prompt": (
            "You are helping someone pitch a story to a journalist/editor at "
            "{domain} (location: {location}). Recipient: {name}, {title}. "
            "Their background/beat: {background}. Story angle: {role}. "
            "Write a concise (<130 words) pitch that connects the angle to their "
            "beat, leads with why it matters now, and offers a quick chat or more "
            "info. Newsworthy and specific, no fluff."
        ),
        "fallback_subject": "Story idea: {role}",
    },
    # Use case E — podcast guesting.
    # Input: podcast/network domain + your topic/expertise (via --role). Target
    # content/editorial contacts; enrich from the show's site to reference it.
    "podcast": {
        "source": "hunter",
        "requires": ["domain", "role"],
        "targeting": {"department": "communication,marketing,management", "seniority": "senior,executive"},
        "enrich": "web",
        "personalizer": "claude",
        "throttle_seconds": 45,
        "prompt": (
            "You are helping someone pitch themselves as a podcast guest to the "
            "team behind {domain} (location: {location}). Recipient: {name}, "
            "{title}. Show context: {background}. The guest's topic/expertise: "
            "{role}. Write a concise (<130 words) pitch that connects their "
            "expertise to the show's audience, names one or two concrete episode "
            "angles, and asks if a guest slot makes sense. Specific, zero flattery."
        ),
        "fallback_subject": "Guest idea for your show: {role}",
    },
    # Use case F — partnerships / business development.
    # Input: target company + what you propose partnering on (via --role).
    "partnerships": {
        "source": "hunter",
        "requires": ["company", "role"],
        "targeting": {"department": "executive,management,sales", "seniority": "executive,senior"},
        "enrich": "web",
        "personalizer": "claude",
        "throttle_seconds": 40,
        "prompt": (
            "You are helping someone propose a partnership to {company} "
            "(location: {location}). Recipient: {name}, {title}. Company "
            "context: {background}. The proposed collaboration: {role}. "
            "Write a concise (<140 words) email that states the mutual benefit "
            "in one or two lines, shows you understand what {company} does, and "
            "asks for a short exploratory call. Credible and concrete, no hype."
        ),
        "fallback_subject": "Partnership idea for {company}",
    },
    # Use case G — recruiting.
    # Input: company where the candidate works + the role you're hiring for
    # (via --role). Targets engineering/technical people rather than HR.
    "recruiting": {
        "source": "hunter",
        "requires": ["company", "role"],
        "targeting": {"department": "it", "seniority": "senior"},
        "enrich": None,
        "personalizer": "claude",
        "throttle_seconds": 45,
        "prompt": (
            "You are helping a recruiter/hiring manager write a short, respectful "
            "cold email to a potential candidate currently at {company}. "
            "Recipient: {name}, {title}. The open role: {role} "
            "(location: {location}). Write a concise (<120 words) note that says "
            "why their profile specifically fits, gives one honest reason the "
            "role is compelling, and invites a low-pressure chat. Human tone, no "
            "recruiter clichés, no exclamation marks."
        ),
        "fallback_subject": "{role} — would love to chat",
    },
}


def get_campaign(name: str) -> dict[str, Any]:
    if name not in CAMPAIGNS:
        raise KeyError(
            f"Unknown campaign '{name}'. Available: {', '.join(CAMPAIGNS)}"
        )
    return CAMPAIGNS[name]
