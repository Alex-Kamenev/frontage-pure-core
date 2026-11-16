"""New synthetic tests; original test files and corpora are not copied."""

import datetime as dt
from dataclasses import FrozenInstanceError, replace
import hashlib
import io
import unittest

try:
    from PIL import Image, PngImagePlugin
except ImportError:
    Image = None
    PngImagePlugin = None

from frontage.gate import (
    MAX_LINE_LENGTH, Content, Facts, Tier, scan, strip_soft, summarise,
)
from frontage.ingest import (
    ACCEPTED_MIME, BURST_QUIET_SECONDS, MAX_MEDIA_BYTES, burst_is_closed,
    content_hash, is_accepted_media, strip_location_metadata,
)
from frontage.publish import (
    COOLDOWN_SECONDS, FAILURE_THRESHOLD, BreakerPhase, BreakerState,
    Decision, Outcome, PublishRequest, breaker_after, decide,
    idempotency_key, semantic_hash,
)

NOW = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)


class GateTests(unittest.TestCase):
    def test_plain_synthetic_content_is_clean(self):
        result = scan(Content(caption="A synthetic note."))
        self.assertTrue(result.clean)
        self.assertFalse(result.blocked)
        self.assertEqual(result.findings, ())

    def test_every_populated_field_is_scanned(self):
        content = Content(caption="certified", alt_text="certified",
                          overlay_text="certified", first_comment="certified",
                          hashtags=("#licensed",), variants={"demo": "certified"})
        fields = {finding.field_name for finding in scan(content).hard}
        self.assertEqual(fields, {"caption", "alt_text", "overlay_text", "first_comment",
                                  "hashtags", "variant:demo"})

    def test_price_requires_matching_caller_fact(self):
        content = Content(caption="Synthetic price $17.25.")
        self.assertTrue(scan(content).blocked)
        self.assertTrue(scan(content, Facts(prices=frozenset({"$17.25"}))).clean)
        self.assertTrue(scan(content, Facts(prices=frozenset({"$18.25"}))).blocked)

    def test_claim_matching_normalizes_case_and_whitespace(self):
        content = Content(caption="certified")
        self.assertTrue(scan(content).blocked)
        self.assertTrue(scan(content, Facts(whitelisted_claims=frozenset({" CERTIFIED "}))).clean)

    def test_forbidden_phrase_keeps_word_boundaries(self):
        facts = Facts(forbidden_claims=frozenset({"synthetic phrase"}))
        self.assertTrue(scan(Content(caption="A synthetic phrase here."), facts).blocked)
        self.assertTrue(scan(Content(caption="A synthetic phrases here."), facts).clean)

    def test_bare_domain_is_soft_and_can_be_allowed(self):
        content = Content(caption="example.com")
        result = scan(content)
        self.assertFalse(result.blocked)
        self.assertEqual([finding.rule_id for finding in result.soft], ["link.bare_domain"])
        self.assertTrue(scan(content, Facts(allowed_domains=frozenset({"EXAMPLE.COM"}))).clean)

    def test_url_is_hard_even_when_bare_domain_is_allowed(self):
        result = scan(Content(caption="https://example.com/demo"),
                      Facts(allowed_domains=frozenset({"example.com"})))
        self.assertTrue(result.blocked)
        self.assertIn("link.url", {finding.rule_id for finding in result.hard})

    def test_handle_soft_removal_and_allowlist(self):
        text = "Note @demo_user"
        result = scan(Content(caption=text))
        self.assertEqual(strip_soft(text, result.findings), "Note")
        self.assertTrue(scan(Content(caption=text),
                             Facts(allowed_handles=frozenset({"demo_user"}))).clean)

    def test_four_soft_findings_escalate(self):
        result = scan(Content(caption="@alpha @bravo @charlie @delta"))
        self.assertTrue(result.blocked)
        self.assertEqual(len(result.hard), 4)
        self.assertEqual(result.soft, ())

    def test_line_length_boundary(self):
        self.assertTrue(scan(Content(caption="x" * MAX_LINE_LENGTH)).clean)
        result = scan(Content(caption="x" * (MAX_LINE_LENGTH + 1)))
        self.assertEqual([finding.rule_id for finding in result.soft], ["style.long_line"])

    def test_summary_keeps_rule_field_and_severity(self):
        summary = summarise(scan(Content(overlay_text="certified")))
        self.assertTrue(summary["blocked"])
        self.assertEqual(summary["soft"], [])
        self.assertEqual(summary["hard"][0]["rule"], "claim.unsubstantiated")
        self.assertEqual(summary["hard"][0]["field"], "overlay_text")


class IngestTests(unittest.TestCase):
    def test_raw_byte_identity_is_sha256(self):
        data = b"invented fixture bytes"
        self.assertEqual(content_hash(data), hashlib.sha256(data).hexdigest())
        self.assertNotEqual(content_hash(data), content_hash(data + b"!"))

    def test_accepted_mime_labels(self):
        for mime_type in ACCEPTED_MIME:
            with self.subTest(mime_type=mime_type):
                self.assertEqual(is_accepted_media(mime_type, 1), (True, ""))

    def test_size_boundaries(self):
        self.assertEqual(is_accepted_media("image/png", MAX_MEDIA_BYTES), (True, ""))
        for size in (-1, 0, MAX_MEDIA_BYTES + 1):
            accepted, reason = is_accepted_media("image/png", size)
            self.assertFalse(accepted)
            self.assertTrue(reason)

    def test_unsupported_mime_label_is_rejected(self):
        accepted, reason = is_accepted_media("application/octet-stream", 1)
        self.assertFalse(accepted)
        self.assertTrue(reason)

    def test_burst_closure_boundary(self):
        before = NOW + dt.timedelta(seconds=BURST_QUIET_SECONDS - 1)
        boundary = NOW + dt.timedelta(seconds=BURST_QUIET_SECONDS)
        self.assertFalse(burst_is_closed(NOW, before))
        self.assertTrue(burst_is_closed(NOW, boundary))

    def test_nonimage_data_passes_through_unchanged(self):
        data = b"invented nonimage fixture"
        self.assertEqual(strip_location_metadata(data, "video/mp4"), data)

    @unittest.skipIf(Image is None, "Pillow is not installed; image branch unverified")
    def test_synthetic_png_reencoding_drops_text_metadata(self):
        image = Image.new("RGB", (2, 2), (10, 20, 30))
        metadata = PngImagePlugin.PngInfo()
        metadata.add_text("fixture", "synthetic-only")
        source = io.BytesIO()
        image.save(source, format="PNG", pnginfo=metadata)
        result = strip_location_metadata(source.getvalue(), "image/png")
        with Image.open(io.BytesIO(result)) as cleaned:
            self.assertEqual(cleaned.size, (2, 2))
            self.assertEqual(cleaned.getpixel((0, 0)), (10, 20, 30))
            self.assertNotIn("fixture", cleaned.info)

    @unittest.skipIf(Image is None, "Pillow is not installed; image branch unverified")
    def test_unreadable_image_is_not_returned(self):
        with self.assertRaises(ValueError):
            strip_location_metadata(b"not an image: synthetic fixture", "image/png")


class PublishTests(unittest.TestCase):
    def request(self, **changes):
        digest = semantic_hash(caption="Synthetic note")
        base = PublishRequest("synthetic-post", "synthetic-channel", True,
                              digest, digest, False, None, BreakerState())
        return replace(base, **changes)

    def test_content_hash_is_stable_and_field_boundaries_matter(self):
        first = semantic_hash(caption="a|b", alt_text="")
        self.assertEqual(first, semantic_hash(caption="a|b", alt_text=""))
        self.assertNotEqual(first, semantic_hash(caption="a", alt_text="b"))
        self.assertNotEqual(first, semantic_hash(caption="a|b", asset_hash="changed"))

    def test_dispatch_key_is_derived_and_changes_with_content(self):
        kwargs = dict(post_id="synthetic-post", platform="synthetic-channel", content_hash="one")
        key = idempotency_key(**kwargs)
        self.assertEqual(key, idempotency_key(**kwargs))
        self.assertEqual(len(key), 48)
        self.assertNotEqual(key, idempotency_key(**dict(kwargs, content_hash="two")))

    def test_closed_breaker_allows(self):
        self.assertTrue(BreakerState().allows(NOW))

    def test_retryable_failures_open_at_threshold(self):
        state = BreakerState()
        for _ in range(FAILURE_THRESHOLD - 1):
            state = breaker_after(state, Outcome.FAILED_RETRYABLE, NOW)
        self.assertEqual(state.phase, BreakerPhase.CLOSED)
        state = breaker_after(state, Outcome.FAILED_RETRYABLE, NOW)
        self.assertEqual(state.phase, BreakerPhase.OPEN)
        self.assertFalse(state.allows(NOW))

    def test_open_breaker_cooldown_boundary(self):
        state = BreakerState(BreakerPhase.OPEN, FAILURE_THRESHOLD, NOW)
        self.assertFalse(state.allows(NOW + dt.timedelta(seconds=COOLDOWN_SECONDS - 1)))
        self.assertTrue(state.allows(NOW + dt.timedelta(seconds=COOLDOWN_SECONDS)))

    def test_unknown_and_permanent_failure_do_not_change_breaker(self):
        state = BreakerState(consecutive_failures=2)
        self.assertIs(breaker_after(state, Outcome.UNKNOWN, NOW), state)
        self.assertIs(breaker_after(state, Outcome.FAILED_PERMANENT, NOW), state)

    def test_success_resets_breaker(self):
        state = BreakerState(BreakerPhase.OPEN, FAILURE_THRESHOLD, NOW)
        self.assertEqual(breaker_after(state, Outcome.PUBLISHED, NOW), BreakerState())

    def test_request_is_immutable(self):
        with self.assertRaises(FrozenInstanceError):
            self.request().approved = False

    def test_already_published_guard_has_priority(self):
        request = self.request(already_published=True, approved=False,
                               current_semantic_hash="changed", kill_switch=True,
                               token_expires_at=NOW)
        self.assertEqual(decide(request, NOW), Decision.SKIP_ALREADY_PUBLISHED)

    def test_approval_precedes_content_and_deferrals(self):
        request = self.request(approved=False, current_semantic_hash="changed", kill_switch=True)
        self.assertEqual(decide(request, NOW), Decision.BLOCK_NOT_APPROVED)

    def test_content_change_precedes_kill_switch(self):
        request = self.request(current_semantic_hash="changed", kill_switch=True)
        self.assertEqual(decide(request, NOW), Decision.BLOCK_CONTENT_CHANGED)

    def test_kill_switch_precedes_expiry(self):
        request = self.request(kill_switch=True, token_expires_at=NOW)
        self.assertEqual(decide(request, NOW), Decision.DEFER_KILL_SWITCH)

    def test_expiry_boundary(self):
        self.assertEqual(decide(self.request(token_expires_at=NOW), NOW), Decision.BLOCK_TOKEN_EXPIRED)
        future = NOW + dt.timedelta(seconds=1)
        self.assertEqual(decide(self.request(token_expires_at=future), NOW), Decision.PUBLISH)

    def test_open_breaker_defers_eligible_request(self):
        state = BreakerState(BreakerPhase.OPEN, FAILURE_THRESHOLD, NOW)
        self.assertEqual(decide(self.request(breaker=state), NOW), Decision.DEFER_BREAKER_OPEN)

    def test_eligible_request_returns_decision_without_dispatch(self):
        self.assertEqual(decide(self.request(), NOW), Decision.PUBLISH)


if __name__ == "__main__":
    unittest.main()
