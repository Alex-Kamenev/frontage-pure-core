# Frontage pure core

A standalone component containing existing pure components from a personal, AI-assisted Frontage backend prototype. The extract covers content findings, media-ingest helpers and publication preflight decisions. It contains no application service or publisher implementation.

**License:** [MIT](LICENSE), copyright 2026 Aleksandar Kamenev. The broader application and its service integrations are outside this component release.

## Included implementation

- `frontage.gate`: structured content fields and caller-supplied facts; hard/soft findings; claim, price, contact/link and style heuristics; soft-finding removal and summaries.
- `frontage.ingest`: SHA-256 byte hashing, MIME/size acceptance, quiet-period timing and image re-encoding.
- `frontage.publish`: length-prefixed content/dispatch hashes, circuit-breaker state transitions and ordered preflight decisions for approval, changed content, duplicate dispatch, expiry and deferral.

Selected executable definitions are preserved from the existing implementation. Private product narratives, policy references and comments/docstrings were removed; imports/exports were narrowed. The example and tests are newly written synthetic fixtures, not the original project test corpus. See [Origin](ORIGIN.md).

## Use without installing

Requires Python 3.11 or later. From this directory:

```console
python example.py
python -m unittest discover -s tests -v
```

The example prints a small synthetic result and makes no network or database calls. Most components use only the standard library. The image branch of `strip_location_metadata` requires Pillow; optional metadata tests explicitly skip when it is unavailable. No dependency installation was performed during preparation. Package metadata declares the optional `images` dependency for a later reviewed setup.

```python
from frontage.gate import Content, Facts, scan
from frontage.publish import semantic_hash

content = Content(caption="A synthetic note.")
result = scan(content, Facts())
digest = semantic_hash(caption=content.caption)
```

## Boundaries

No source/test corpus, tenant/account implementation, phone/sender identity helper, tenant-prefixed storage-key function, customer reply, configuration, credential, provider connection, publishing protocol or platform adapter is included. Postgres, RLS, job queues, audit storage and runtime services are outside this extract.

Facts and expiry timestamps are in-memory inputs, not substantiation, authentication or account-management services. The gate uses opinionated regex heuristics; it is not a guarantee of factual accuracy, content safety or privacy. MIME/size acceptance trusts the supplied MIME label and does not inspect file contents. Image re-encoding support depends on the installed Pillow codecs, can change image bytes, and does not process video metadata. No general metadata-removal or security certification is claimed.

The preflight functions compute decisions; callers remain responsible for enforcing them. A hash-derived key alone does not establish provider idempotency, and the breaker helpers do not coordinate concurrent workers. There are no live publication or integration results for this candidate.

## Verification status

Independent isolated verification passed all 34 newly authored synthetic tests on Python 3.12 with Pillow 12.3.0, with no skipped tests. The synthetic example also passed. Network connections were blocked and the subprocess environment was restricted; no database or provider connection was used. Historical tests of the broader original pure core are separate evidence, not a passing count for this extraction.

## License

[MIT](LICENSE). The scoped component release does not cover any excluded application material.

## Install and CI

```console
python -m pip install ".[images]"
python -m unittest discover -s tests -v
python example.py
```

The CI workflow runs the synthetic suite, example and wheel build on Python 3.11,
3.12 and 3.14. [Portfolio case study](https://alex-kamenev.github.io/work/frontage/).
