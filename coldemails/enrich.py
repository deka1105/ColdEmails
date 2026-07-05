"""Background enrichment for personalization.

Some campaigns (fundraising, PR) research each prospect before writing. The
``Enricher`` interface fills ``Person.background``; the engine skips this step
entirely when a campaign sets ``enrich: None``.

``WebEnricher`` does real research: it fetches a few likely pages on the
prospect's domain (home, /about, /team, /portfolio), strips them to text, and —
if an Anthropic key is available — asks Claude to distill a 1–2 sentence
background focused on thesis/beat. Without a key it falls back to a cleaned
text excerpt, and if fetching fails it falls back to the provider payload.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from html.parser import HTMLParser
from typing import Optional

import requests

from .config import env
from .models import Person

FETCH_TIMEOUT = 12
MAX_TEXT_CHARS = 6000  # cap text sent to the model / stored
CANDIDATE_PATHS = ["", "/about", "/about-us", "/team", "/portfolio", "/thesis"]
USER_AGENT = "ColdEmailsBot/0.1 (+research)"
DDG_HTML = "https://html.duckduckgo.com/html/"
SERPER_URL = "https://google.serper.dev/search"


def _claude_client():
    """Shared optional Claude client; ``None`` when no key/SDK available."""
    if not env("ANTHROPIC_API_KEY"):
        return None
    try:
        from anthropic import Anthropic

        return Anthropic(api_key=env("ANTHROPIC_API_KEY"))
    except Exception:
        return None


class Enricher(ABC):
    name: str = "base"

    @abstractmethod
    def enrich(self, person: Person) -> Person:
        """Populate ``person.background`` in place and return it."""
        ...


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping script/style/noscript content."""

    _SKIP = {"script", "style", "noscript", "head", "svg"}

    def __init__(self) -> None:
        super().__init__()
        self._chunks: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._chunks.append(text)

    @property
    def text(self) -> str:
        return " ".join(self._chunks)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return ""
    return " ".join(parser.text.split())


class WebEnricher(Enricher):
    name = "web"

    def __init__(self) -> None:
        self._cache: dict[str, str] = {}  # domain -> fetched text (per run)
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        # Claude summarizer is optional; only used if a key is present.
        self._client = _claude_client()

    def enrich(self, person: Person) -> Person:
        if person.background:
            return person
        text = self._fetch_domain_text(person.domain) if person.domain else ""
        if text:
            person.background = self._summarize(person, text) or self._payload_fallback(person)
        else:
            person.background = self._payload_fallback(person)
        return person

    # --- fetching --------------------------------------------------------
    def _fetch_domain_text(self, domain: str) -> str:
        domain = domain.strip().lower()
        if domain in self._cache:
            return self._cache[domain]

        collected: list[str] = []
        for scheme in ("https://", "http://"):
            for path in CANDIDATE_PATHS:
                url = f"{scheme}{domain}{path}"
                try:
                    resp = self._session.get(url, timeout=FETCH_TIMEOUT)
                except requests.RequestException:
                    continue
                if resp.status_code == 200 and "text/html" in resp.headers.get(
                    "Content-Type", ""
                ):
                    txt = _html_to_text(resp.text)
                    if txt:
                        collected.append(txt)
                if len(" ".join(collected)) >= MAX_TEXT_CHARS:
                    break
            if collected:
                break  # got pages over https; don't retry http

        text = " ".join(collected)[:MAX_TEXT_CHARS]
        self._cache[domain] = text
        return text

    # --- distilling ------------------------------------------------------
    def _summarize(self, person: Person, text: str) -> str:
        if not self._client:
            # No model available: return a trimmed excerpt as the background.
            return text[:400].strip()
        prompt = (
            f"From the following website text for {person.company or person.domain}, "
            f"write 1-2 sentences describing this organization's focus, thesis, or "
            f"editorial beat — the kind of context useful for a personalized outreach "
            f"email to {person.name} ({person.title or 'a contact'} there). "
            f"Be factual; if unclear, say so briefly.\n\n---\n{text[:MAX_TEXT_CHARS]}"
        )
        try:
            from .personalize import CLAUDE_MODEL

            resp = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=160,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(
                b.text for b in resp.content if b.type == "text"
            ).strip()
        except Exception:
            return ""

    def _payload_fallback(self, person: Person) -> str:
        parts: list[str] = []
        if person.title:
            parts.append(person.title)
        if person.company:
            parts.append(f"at {person.company}")
        if person.domain:
            parts.append(f"({person.domain})")
        return " ".join(parts) or "No public background found."


class SearchEnricher(Enricher):
    """Research the *individual* via a web search API.

    Unlike ``WebEnricher`` (which reads the org's own site), this searches for
    the person by name + company/title to surface their bio, articles, talks,
    or profiles, then distills a background with Claude.

    Backend is pluggable via ``SEARCH_PROVIDER``:
      - ``serper`` (default when ``SERPER_API_KEY`` is set) — Google via serper.dev
      - ``ddg`` (default, no key) — DuckDuckGo HTML result snippets
    """

    name = "search"

    def __init__(self) -> None:
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": USER_AGENT})
        self._client = _claude_client()
        self._serper_key = env("SERPER_API_KEY")
        self._provider = env(
            "SEARCH_PROVIDER", "serper" if self._serper_key else "ddg"
        )
        self._cache: dict[str, str] = {}  # query -> snippets

    def enrich(self, person: Person) -> Person:
        if person.background or not person.name:
            return person
        query = " ".join(
            p for p in [person.name, person.company, person.title] if p
        )
        snippets = self._search(query)
        if snippets:
            person.background = self._summarize(person, snippets) or snippets[:400]
        else:
            person.background = self._payload_fallback(person)
        return person

    # --- search backends -------------------------------------------------
    def _search(self, query: str) -> str:
        if query in self._cache:
            return self._cache[query]
        try:
            if self._provider == "serper" and self._serper_key:
                text = self._search_serper(query)
            else:
                text = self._search_ddg(query)
        except requests.RequestException:
            text = ""
        text = " ".join(text.split())[:MAX_TEXT_CHARS]
        self._cache[query] = text
        return text

    def _search_serper(self, query: str) -> str:
        resp = self._session.post(
            SERPER_URL,
            headers={"X-API-KEY": self._serper_key, "Content-Type": "application/json"},
            json={"q": query, "num": 6},
            timeout=FETCH_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        parts: list[str] = []
        if kg := data.get("knowledgeGraph"):
            parts.append(kg.get("description", ""))
        for r in data.get("organic", [])[:6]:
            parts.append(f"{r.get('title', '')}. {r.get('snippet', '')}")
        return " ".join(p for p in parts if p)

    def _search_ddg(self, query: str) -> str:
        resp = self._session.post(
            DDG_HTML, data={"q": query}, timeout=FETCH_TIMEOUT
        )
        resp.raise_for_status()
        return _ddg_snippets(resp.text)

    # --- distilling ------------------------------------------------------
    def _summarize(self, person: Person, snippets: str) -> str:
        if not self._client:
            return snippets[:400].strip()
        prompt = (
            f"From these web search results about {person.name} "
            f"({person.title or ''} {('at ' + person.company) if person.company else ''}), "
            f"write 1-2 factual sentences about their background, focus, or notable "
            f"work — useful context for a personalized outreach email. If the results "
            f"seem to be about a different person or are inconclusive, say so.\n\n"
            f"---\n{snippets[:MAX_TEXT_CHARS]}"
        )
        try:
            from .personalize import CLAUDE_MODEL

            resp = self._client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=160,
                messages=[{"role": "user", "content": prompt}],
            )
            return "".join(b.text for b in resp.content if b.type == "text").strip()
        except Exception:
            return ""

    def _payload_fallback(self, person: Person) -> str:
        parts: list[str] = []
        if person.title:
            parts.append(person.title)
        if person.company:
            parts.append(f"at {person.company}")
        return " ".join(parts) or "No public background found."


class _DDGSnippetParser(HTMLParser):
    """Extract text inside <a class="result__snippet"> from DDG HTML results."""

    def __init__(self) -> None:
        super().__init__()
        self._snippets: list[str] = []
        self._capture = False

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            classes = dict(attrs).get("class", "") or ""
            if "result__snippet" in classes:
                self._capture = True

    def handle_endtag(self, tag):
        if tag == "a" and self._capture:
            self._capture = False

    def handle_data(self, data):
        if self._capture:
            text = data.strip()
            if text:
                self._snippets.append(text)

    @property
    def snippets(self) -> str:
        return " ".join(self._snippets)


def _ddg_snippets(html: str) -> str:
    parser = _DDGSnippetParser()
    try:
        parser.feed(html)
    except Exception:
        return ""
    return parser.snippets


_ENRICHERS: dict[str, type[Enricher]] = {
    "web": WebEnricher,
    "search": SearchEnricher,
}


def get_enricher(name: Optional[str]) -> Optional[Enricher]:
    if not name:
        return None
    if name not in _ENRICHERS:
        raise ValueError(
            f"Unknown enricher '{name}'. Available: {', '.join(_ENRICHERS)}"
        )
    return _ENRICHERS[name]()
