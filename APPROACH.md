# Approach and decision log

## Input assumption

Only the assignment PDF was delivered; its referenced manuals were absent. I created small, realistic replacements and made that fact visible rather than pretending they are official. They include duplicate sibling headings, a level jump, a Setext heading, heading-like text inside a fence, a table, and body changes/additions between versions.

## Data model

`Document -> DocumentVersion -> NodeSnapshot` stores immutable versions. `LogicalNode` is the cross-version identity; each snapshot contains its heading, level, body, full text, parent logical ID, order, and SHA-256 content hash. `SelectionItem` points to a snapshot row—not merely the latest logical node—so selections always reconstruct their original text.

Generated output lives in a JSON document store keyed by selection. This satisfies the requested relational/NoSQL separation without requiring an evaluator to install MongoDB. Writes use a flushed temporary file followed by atomic replacement, although cross-process locking and richer querying would still need strengthening in production.

## Parsing

The parser is intentionally scoped to the supplied documents. It recognizes ATX and Setext headings, ignores heading-like lines in backtick or tilde fences, preserves tables/lists/code in bodies, keeps duplicate headings distinct using an occurrence suffix, and parents a skipped level beneath the nearest preceding lower-level heading. It refuses non-empty text before the first heading and rejects unclosed fences instead of silently discarding, hiding, or inventing structure.

My first simple design—treating every `#` line as a heading—would incorrectly split the fenced display example. Manual inspection plus a focused test exposed that. A heading stack test exposed the skipped-level case, and an identity test exposed duplicate-title collisions.

## Version matching

Logical identity is UUIDv5 over document key plus normalized ancestor-title path and same-title sibling occurrence. This is deterministic, explainable, and correctly treats body edits as the same node. Hashes decide whether content changed. It breaks when a heading or ancestor is renamed, or identical siblings are reordered; these appear removed/added rather than being guessed together. Production could add conservative fuzzy candidates requiring human confirmation.

Diffs use a text similarity score and a short unified diff, with explicit `added`, `removed`, `changed`, and `unchanged` states. Staleness remains deliberately binary: any hash change is stale. A punctuation edit and a changed pressure threshold both trigger it. That is conservative and appropriate for regulated source text, but it does not rank clinical impact.

## LLM behavior

The prompt constrains the model to selected source text and requires 3–5 executable cases with source node IDs. Pydantic validates shape and cardinality, and code rejects citations outside the selection. Invalid output is retried with concise error feedback. Exhausted retries return 502 and nothing is persisted—malformed cases are never silently accepted.

Repeated generation reuses the selection's stored result for reproducibility and cost control. `force=true` is an explicit replacement policy. Each record stores its document key and exact source version/hash pairs, so retrieval compares them to the latest version of the correct document and reports `fresh`, `stale`, or `removed`.

## Decision log

1. **Most likely silent wrong result:** Cross-version node matching can confidently associate the wrong duplicate after reordering. I catch this with identity/tree snapshot tests, review unmatched/changed-node reports, and would add human confirmation for ambiguous production matches.
2. **Simplicity over correctness:** A JSON directory replaces MongoDB and path/occurrence matching replaces semantic matching. Concurrent generation writes and heading renames would break first in production.
3. **Unhandled input:** HTML headings are unsupported. If a document contains only HTML headings, ingestion fails with “no headings”; embedded HTML inside a recognized section is retained as body text rather than interpreted.

## With more time

I would add migration tooling, atomic JSON writes/locking or MongoDB, document-key-scoped version lookup, property-based parser tests, conservative rename detection, impact classification for numeric requirement changes, provider observability, and an evaluator-approved corpus built from the official missing manuals.
