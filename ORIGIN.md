# Origin and extraction

This component is extracted from the implemented pure gate, ingest and publish-decision modules of a personal Frontage backend prototype. The original project was developed with AI assistance; AI assistance was also used for this isolation and its newly authored synthetic example/tests.

## Preserved core

The extract retains the executable logic of the selected original definitions: content/fact/result dataclasses and gate rules; raw-byte hashing, MIME/size checks, burst timing and image re-encoding; and content identity, breaker transitions and publication preflight decisions.

Extraction removed original comments/docstrings and supplied neutral module descriptions. Imports and public exports were narrowed to the retained boundary. An AST comparison during authoring checked that the selected executable definitions were unchanged after removing docstrings. This preservation check is not a runtime test result or a security review.

## Excluded material

Original test files and their text corpora were not copied. The synthetic tests and example were written for this candidate and contain invented text, identifiers, timestamps and in-memory image fixtures. Historical original-suite results do not establish their passing count.

The extract omits business plans, operational policy documents, account connections, tenant/runtime/configuration modules, sender/phone helpers, tenant storage keys, customer-reply copy, platform names and the publisher connection protocol. It also excludes Postgres/RLS, job workers, audit integration, media assets and external-service implementations.

This is an existing component extraction, not a newly completed SaaS or evidence of deployment. Fresh standalone verification passed 34 synthetic tests. The scoped component release is licensed under MIT, copyright 2026 Aleksandar Kamenev. No original project was modified.
