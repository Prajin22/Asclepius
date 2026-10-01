"""IP-SAKTI Sahayak — the backend domain for PRODUCT=ip_sakti.

Phase 1 holds only the demo accounts. Shared infrastructure (auth, audit,
storage, providers) lives where it always has; this package may import it, and
nothing outside this package imports from here except the seed entry point and
the model registry.
"""
