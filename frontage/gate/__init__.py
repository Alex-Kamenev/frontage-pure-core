"""Pure content-gate components adapted from a personal prototype."""
from __future__ import annotations
import enum
import re
from dataclasses import dataclass, field
from typing import Any
__all__ = ['Content', 'Facts', 'Finding', 'GateResult', 'Tier', 'scan', 'strip_soft', 'summarise']

class Tier(enum.StrEnum):
    HARD = 'hard'
    SOFT = 'soft'

@dataclass(frozen=True, slots=True)
class Finding:
    rule_id: str
    tier: Tier
    field_name: str
    span: str
    message: str

@dataclass(frozen=True, slots=True)
class Content:
    caption: str = ''
    alt_text: str = ''
    overlay_text: str = ''
    first_comment: str = ''
    hashtags: tuple[str, ...] = ()
    variants: dict[str, str] = field(default_factory=dict)

    def fields(self) -> dict[str, str]:
        out = {'caption': self.caption, 'alt_text': self.alt_text, 'overlay_text': self.overlay_text, 'first_comment': self.first_comment, 'hashtags': ' '.join(self.hashtags)}
        out.update({f'variant:{k}': v for k, v in self.variants.items()})
        return {k: v for k, v in out.items() if v}

@dataclass(frozen=True, slots=True)
class Facts:
    prices: frozenset[str] = frozenset()
    whitelisted_claims: frozenset[str] = frozenset()
    forbidden_claims: frozenset[str] = frozenset()
    allowed_domains: frozenset[str] = frozenset()
    allowed_handles: frozenset[str] = frozenset()

@dataclass(frozen=True, slots=True)
class GateResult:
    findings: tuple[Finding, ...]
    blocked: bool

    @property
    def hard(self) -> tuple[Finding, ...]:
        return tuple((f for f in self.findings if f.tier is Tier.HARD))

    @property
    def soft(self) -> tuple[Finding, ...]:
        return tuple((f for f in self.findings if f.tier is Tier.SOFT))

    @property
    def clean(self) -> bool:
        return not self.findings
_URL = re.compile('(?:https?://|www\\.)\\S+|\\b(?:bit\\.ly|t\\.co|tinyurl\\.com|goo\\.gl|ow\\.ly|buff\\.ly|is\\.gd)/\\S+', re.IGNORECASE)
_ABUSE_TLD = re.compile('\\b\\w+\\.(?:xyz|top|click|link|gq|cf|tk|ml|zip|mov)\\b', re.IGNORECASE)
_EMAIL = re.compile('\\b[\\w.+-]+@[\\w-]+\\.[a-z]{2,}\\b', re.IGNORECASE)
_PHONE = re.compile('(?:\\+?1[-.\\s])?\\(?\\b\\d{3}\\b\\)?[-.\\s]\\d{3}[-.\\s]\\d{4}\\b')
_DOMAINISH = re.compile('\\b(?!\\d+\\.\\d+\\b)[a-z0-9][\\w-]*\\.(?:com|net|org|io|co|us|biz|info|shop)\\b')
_HANDLE = re.compile('(?<![\\w/])@([A-Za-z0-9_.]{2,30})\\b')
_SCAM = re.compile('\\b(?:wire\\s+transfer|western\\s+union|gift\\s+cards?|crypto\\s+payment|act\\s+now|limited\\s+time\\s+only|risk[-\\s]free|click\\s+here|dm\\s+me\\s+to\\s+claim|100%\\s+(?:free|guaranteed)|no\\s+credit\\s+check)\\b', re.IGNORECASE)
_CLAIM = re.compile('(?:\\b(?:guarantee[sd]?|guaranteeing|warrant(?:y|ies|ied)|licen[sc]ed|insured|bonded|certified|accredited|lifetime\\s+\\w+|number\\s+one|best\\s+(?:in|price)|cheapest|lowest\\s+price|unbeatable|award[-\\s]winning)\\b|#\\s?1(?!\\d))', re.IGNORECASE)
_SQUASHED_CLAIMS = frozenset({'bestintown', 'bestprice', 'bestroofer', 'numberone', 'cheapest', 'lowestprice', 'unbeatable', 'awardwinning', 'lifetimewarranty', 'licensedandinsured', 'guaranteedwork', 'satisfactionguaranteed'})
_REGULATED = re.compile('\\b(?:diagnos\\w+|treat(?:s|ed|ment)?\\s+(?:your|the)\\s+\\w+|cure[sd]?|tax[-\\s]deductible|write[-\\s]off|legal\\s+advice|we\\s+recommend\\s+you\\s+(?:sue|file)|investment\\s+(?:advice|return)|FDA[-\\s]approved|EPA[-\\s]certified\\s+for)\\b', re.IGNORECASE)
_MONEY = re.compile('\\$\\s?\\d[\\d,]*(?:\\.\\d{2})?')
_PROMISE = re.compile('\\b(?:same[-\\s]day|24/7|24\\s*hours?\\s+a\\s+day|within\\s+\\d+\\s+(?:minutes?|hours?)|open\\s+(?:24|all\\s+night)|always\\s+available|next[-\\s]day\\s+service)\\b', re.IGNORECASE)
SOFT_ESCALATION_THRESHOLD = 3
MAX_LINE_LENGTH = 300

def _normalise_claim(text: str) -> str:
    return re.sub('\\s+', ' ', text.strip().lower())

def scan(content: Content, facts: Facts | None=None) -> GateResult:
    facts = facts or Facts()
    findings: list[Finding] = []
    for name, text in content.fields().items():
        findings.extend(_scan_field(name, text, facts))
    hard = [f for f in findings if f.tier is Tier.HARD]
    soft = [f for f in findings if f.tier is Tier.SOFT]
    if not hard and len(soft) > SOFT_ESCALATION_THRESHOLD:
        findings = [Finding(f.rule_id, Tier.HARD, f.field_name, f.span, f'{f.message} (escalated: {len(soft)} soft findings on one post)') for f in findings]
        hard = findings
    return GateResult(findings=tuple(findings), blocked=bool(hard))

def _scan_field(name: str, text: str, facts: Facts) -> list[Finding]:
    out: list[Finding] = []

    def hard(rule: str, span: str, msg: str) -> None:
        out.append(Finding(rule, Tier.HARD, name, span, msg))

    def soft(rule: str, span: str, msg: str) -> None:
        out.append(Finding(rule, Tier.SOFT, name, span, msg))
    for m in _URL.finditer(text):
        hard('link.url', m.group(0), 'a link we did not put there')
    for m in _ABUSE_TLD.finditer(text):
        hard('link.abuse_tld', m.group(0), 'domain on an abuse-prone TLD')
    for m in _EMAIL.finditer(text):
        hard('contact.email', m.group(0), 'an e-mail address')
    for m in _PHONE.finditer(text):
        hard('contact.phone', m.group(0), 'a phone number we cannot verify')
    for m in _SCAM.finditer(text):
        hard('scam.vocabulary', m.group(0), 'scam-adjacent phrasing')
    for m in _REGULATED.finditer(text):
        hard('regulated.advice', m.group(0), 'regulated advice vocabulary')
    lowered = text.lower()
    for phrase in facts.forbidden_claims:
        needle = _normalise_claim(phrase)
        if needle and re.search(f'\\b{re.escape(needle)}\\b', lowered):
            hard('tenant.forbidden', phrase, "on this tenant's forbidden list")
    for m in _CLAIM.finditer(text):
        span = m.group(0)
        if _normalise_claim(span) in {_normalise_claim(c) for c in facts.whitelisted_claims}:
            continue
        hard('claim.unsubstantiated', span, 'a claim with no recorded substantiation')
    for m in _MONEY.finditer(text):
        span = m.group(0)
        if _normalise_claim(span).replace(' ', '') in {_normalise_claim(p).replace(' ', '') for p in facts.prices}:
            continue
        hard('fact.price', span, 'a price that traces to no recorded quote')
    if name == 'hashtags':
        squashed = re.sub('[^a-z0-9]', '', text.lower())
        whitelisted = {re.sub('[^a-z0-9]', '', c.lower()) for c in facts.whitelisted_claims}
        for phrase in _SQUASHED_CLAIMS:
            if phrase in squashed and phrase not in whitelisted:
                hard('claim.unsubstantiated', f'#{phrase}', 'a superlative claim in a hashtag')
    for m in _PROMISE.finditer(text):
        span = m.group(0)
        if _normalise_claim(span) in {_normalise_claim(c) for c in facts.whitelisted_claims}:
            continue
        hard('fact.availability', span, 'an availability promise with nothing behind it')
    for m in _DOMAINISH.finditer(text):
        if m.group(0).lower() in {d.lower() for d in facts.allowed_domains}:
            continue
        soft('link.bare_domain', m.group(0), 'a bare domain')
    for m in _HANDLE.finditer(text):
        if m.group(1).lower() in {h.lstrip('@').lower() for h in facts.allowed_handles}:
            continue
        soft('mention.foreign_handle', m.group(0), "a handle that is not this tenant's")
    for line in text.splitlines():
        if len(line) > MAX_LINE_LENGTH:
            soft('style.long_line', line[:60] + '...', 'line is implausibly long')
    return out

def strip_soft(text: str, findings: tuple[Finding, ...]) -> str:
    out = text
    for finding in findings:
        if finding.tier is Tier.SOFT and finding.span in out:
            out = out.replace(finding.span, '')
    return re.sub('[ \\t]{2,}', ' ', out).strip()

def summarise(result: GateResult) -> dict[str, Any]:
    return {'blocked': result.blocked, 'hard': [{'rule': f.rule_id, 'field': f.field_name, 'span': f.span, 'why': f.message} for f in result.hard], 'soft': [{'rule': f.rule_id, 'field': f.field_name, 'span': f.span, 'why': f.message} for f in result.soft]}
