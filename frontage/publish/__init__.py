"""Pure content identity, breaker transitions and preflight decisions."""
from __future__ import annotations
import datetime as dt
import enum
import hashlib
from dataclasses import dataclass
from typing import assert_never
__all__ = ['Outcome', 'Decision', 'semantic_hash', 'idempotency_key', 'FAILURE_THRESHOLD', 'COOLDOWN_SECONDS', 'BreakerPhase', 'BreakerState', 'breaker_after', 'PublishRequest', 'decide']

class Outcome(enum.StrEnum):
    PUBLISHED = 'published'
    FAILED_RETRYABLE = 'failed_retryable'
    FAILED_PERMANENT = 'failed_permanent'
    UNKNOWN = 'unknown'

class Decision(enum.StrEnum):
    PUBLISH = 'publish'
    SKIP_ALREADY_PUBLISHED = 'skip_already_published'
    DEFER_BREAKER_OPEN = 'defer_breaker_open'
    DEFER_KILL_SWITCH = 'defer_kill_switch'
    BLOCK_CONTENT_CHANGED = 'block_content_changed'
    BLOCK_NOT_APPROVED = 'block_not_approved'
    BLOCK_TOKEN_EXPIRED = 'block_token_expired'

def semantic_hash(*, caption: str, alt_text: str='', overlay_text: str='', hashtags: tuple[str, ...]=(), asset_hash: str='') -> str:
    parts = [caption, alt_text, overlay_text, ' '.join(hashtags), asset_hash]
    payload = ''.join((f'{len(p)}:{p}' for p in parts))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()

def idempotency_key(*, post_id: str, platform: str, content_hash: str) -> str:
    material = ''.join((f'{len(p)}:{p}' for p in (post_id, platform, content_hash)))
    return hashlib.sha256(material.encode('utf-8')).hexdigest()[:48]
FAILURE_THRESHOLD = 5
COOLDOWN_SECONDS = 300

class BreakerPhase(enum.StrEnum):
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'

@dataclass(frozen=True, slots=True)
class BreakerState:
    phase: BreakerPhase = BreakerPhase.CLOSED
    consecutive_failures: int = 0
    opened_at: dt.datetime | None = None

    def allows(self, now: dt.datetime) -> bool:
        if self.phase is BreakerPhase.CLOSED:
            return True
        if self.phase is BreakerPhase.HALF_OPEN:
            return True
        if self.opened_at is None:
            return True
        return (now - self.opened_at).total_seconds() >= COOLDOWN_SECONDS

def breaker_after(state: BreakerState, outcome: Outcome, now: dt.datetime) -> BreakerState:
    match outcome:
        case Outcome.PUBLISHED:
            return BreakerState()
        case Outcome.UNKNOWN:
            return state
        case Outcome.FAILED_PERMANENT:
            return state
        case Outcome.FAILED_RETRYABLE:
            failures = state.consecutive_failures + 1
            if failures >= FAILURE_THRESHOLD:
                return BreakerState(BreakerPhase.OPEN, failures, now)
            return BreakerState(state.phase, failures, state.opened_at)
        case _:
            assert_never(outcome)

@dataclass(frozen=True, slots=True)
class PublishRequest:
    post_id: str
    platform: str
    approved: bool
    approved_semantic_hash: str
    current_semantic_hash: str
    already_published: bool
    token_expires_at: dt.datetime | None
    breaker: BreakerState
    kill_switch: bool = False

def decide(request: PublishRequest, now: dt.datetime) -> Decision:
    if request.already_published:
        return Decision.SKIP_ALREADY_PUBLISHED
    if not request.approved:
        return Decision.BLOCK_NOT_APPROVED
    if request.approved_semantic_hash != request.current_semantic_hash:
        return Decision.BLOCK_CONTENT_CHANGED
    if request.kill_switch:
        return Decision.DEFER_KILL_SWITCH
    if request.token_expires_at is not None and request.token_expires_at <= now:
        return Decision.BLOCK_TOKEN_EXPIRED
    if not request.breaker.allows(now):
        return Decision.DEFER_BREAKER_OPEN
    return Decision.PUBLISH
