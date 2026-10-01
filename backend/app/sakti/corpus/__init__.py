"""The legal and regulatory source corpus: curator ingestion and approval (Phase 2).

    authorities  the official sources a file may come from, and their lanes
    text         the document text, chunks and spans: pure functions, no I/O
    ingest       upload validation, storage, reading a source into pages
    diff         a deterministic line and word diff between two texts
    service      instruments, provisions, versions, the review workflow, status

Nothing in this package writes legal text. Text enters only by being read from
an uploaded file, and leaves only as an exact copy of what was read. There is no
search, retrieval or answering here (later phases), and no AI call: IP-SAKTI's
AI policy permits none, and OCR runs on the local engine only.
"""
