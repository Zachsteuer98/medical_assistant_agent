"""Client identity behind reverse proxies, without trusting forgeable headers."""

from collections.abc import Sequence

UNKNOWN_CLIENT = "unknown"


def client_ip(peer: str | None, forwarded_for: Sequence[str], trusted_hops: int) -> str:
    """The client address for rate limiting.

    Each trusted proxy appends the address it saw to X-Forwarded-For, so the entry
    trusted_hops from the right was written by our own infrastructure; everything left of
    it is client-supplied and ignored. With 0 hops, or a chain shorter than the hop count
    (request did not come through the expected proxies), fall back to the socket peer.
    """
    entries = [e.strip() for value in forwarded_for for e in value.split(",") if e.strip()]
    if trusted_hops and len(entries) >= trusted_hops:
        return entries[-trusted_hops]
    return peer or UNKNOWN_CLIENT
