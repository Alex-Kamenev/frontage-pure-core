# Frontage: pure decision components

This standalone component isolates an implemented part of a personal backend prototype: the decisions made before content is accepted or dispatched. It keeps content findings, media-ingest checks and publication preflight logic together without bringing along a database, queue worker, account connection or publisher service.

The content gate examines structured text fields against caller-supplied facts and produces hard/soft findings. Media helpers cover byte identity, MIME/size checks, quiet-period timing and image re-encoding. Publication helpers derive content/dispatch hashes and evaluate approval, changed content, already-published state, expiry and circuit-breaker deferral in a defined order.

Selected executable definitions retain the original implementation. Private narratives and unrelated integrations were removed; new synthetic tests and an example were authored with AI assistance. This is a component extraction from an independent prototype, not a claim that the broader application ships or works end to end.

**Evidence and limits:** Independent isolated verification passed 34 newly authored synthetic tests on Python 3.12 with Pillow 12.3.0, with no skipped tests; the synthetic example also passed. Earlier original-suite results are separate evidence. No Postgres, RLS, queue, audit, provider-publication, privacy or production guarantee follows from this scope. The scoped component is released under MIT.
