"""Integration with the real MARG backend (BACKEND_MODE=marg).

Implemented against the MARG backend service API after the compatibility
audit (see docs/INTEGRATION.md). The engine reaches MARG data only through
this HTTP adapter; it never connects to the MARG database.
"""
