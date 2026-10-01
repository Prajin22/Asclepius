"""The formulation classifier (IP-SAKTI Phase 3, D-087–D-091).

    model     the vocabulary a classifier tree is written in, and its checks
    trees/    the published trees, as data — one module per version
    registry  which trees exist, their pinned fingerprints, the current one
    engine    the walk: answers in, a question, a stop or a category out
    service   product profiles, sessions, answers, outcomes, confirmation,
              reference links
    presenters  records → API shapes

The decision is made by explicit rules over explicit answers, and by nothing
else: no model, no score, no guess. The same tree version and the same answers
always give the same result. An answer of "unknown" stops the walk where it is
given, and no category comes out of it.

The categories are a product of the user's own answers. They are not a legal
determination, and nothing here says whether a product may be made, sold or
registered.
"""
