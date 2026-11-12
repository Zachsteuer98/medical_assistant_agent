from app.ratelimit import RateLimiter


def test_window_resets_after_expiry():
    now = [0.0]
    limiter = RateLimiter(limit=1, window_s=60, clock=lambda: now[0])
    assert limiter.allow("a")
    assert not limiter.allow("a")
    assert limiter.allow("b")  # per-client
    now[0] = 60.0
    assert limiter.allow("a")
