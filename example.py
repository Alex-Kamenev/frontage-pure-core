"""Exercise the existing pure components with invented values only."""

import datetime as dt
import json

from frontage.gate import Content, Facts, scan, summarise
from frontage.ingest import content_hash
from frontage.publish import BreakerState, PublishRequest, decide, semantic_hash


def main() -> None:
    content = Content(caption="A synthetic note.")
    findings = scan(content, Facts())
    digest = semantic_hash(caption=content.caption)
    request = PublishRequest(
        post_id="synthetic-post",
        platform="synthetic-channel",
        approved=True,
        approved_semantic_hash=digest,
        current_semantic_hash=digest,
        already_published=False,
        token_expires_at=None,
        breaker=BreakerState(),
    )
    now = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
    print(json.dumps({
        "gate": summarise(findings),
        "byte_hash": content_hash(b"invented fixture bytes"),
        "decision_only": decide(request, now).value,
    }, indent=2))


if __name__ == "__main__":
    main()
