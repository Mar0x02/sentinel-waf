"""Built-in fallback content for the error pages feature.

The set of status codes is fixed deliberately - the nginx `error_page`
directives for these codes are baked into the waf-engine image
(waf-engine/error-pages.conf), not rendered dynamically, so adding a new
code here alone does nothing without also adding it there and rebuilding
the image. See CLAUDE.md.

Visual design mirrors the dashboard itself (same dark palette, same
shield mark as frontend/public/favicon.svg) rather than being a generic
nginx-style error page - a blocked visitor's one touchpoint with this
being "a WAF", not a mystery 403.
"""

_STYLE = """
<style>
  :root {
    --page-plane: #1e1e2d;
    --surface-1: #262639;
    --text-primary: #edecf5;
    --text-muted: #70708f;
    --border: rgba(237, 236, 245, 0.1);
    --accent: #22d3ee;
  }
  * { box-sizing: border-box; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", system-ui, sans-serif;
    background: var(--page-plane);
    color: var(--text-primary);
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 100vh;
    margin: 0;
    position: relative;
    overflow: hidden;
  }
  .glow {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 640px;
    height: 640px;
    transform: translate(-50%, -50%);
    background: radial-gradient(circle, color-mix(in srgb, var(--tone) 14%, transparent) 0%, transparent 65%);
    pointer-events: none;
  }
  .card {
    position: relative;
    width: 380px;
    max-width: calc(100vw - 48px);
    background: var(--surface-1);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 36px 32px;
    text-align: center;
    box-shadow: 0 0 0 1px color-mix(in srgb, var(--tone) 8%, transparent), 0 24px 60px rgba(0, 0, 0, 0.45);
  }
  .icon-badge {
    width: 56px;
    height: 56px;
    margin: 0 auto 20px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    color: var(--tone);
    background: color-mix(in srgb, var(--tone) 10%, transparent);
    box-shadow: 0 0 0 1px color-mix(in srgb, var(--tone) 25%, transparent), 0 0 24px color-mix(in srgb, var(--tone) 20%, transparent);
  }
  h1 {
    font-size: 15px;
    font-weight: 600;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    color: var(--tone);
    margin: 0 0 6px;
  }
  .code {
    font-size: 48px;
    font-weight: 700;
    line-height: 1;
    margin: 0 0 14px;
    color: var(--text-primary);
  }
  p {
    color: var(--text-muted);
    font-size: 14px;
    line-height: 1.5;
    margin: 0;
  }
  .brand {
    margin-top: 28px;
    padding-top: 20px;
    border-top: 1px solid var(--border);
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 7px;
    font-size: 12px;
    color: var(--text-muted);
    letter-spacing: 0.04em;
  }
  .brand svg { flex-shrink: 0; }
</style>
"""

_SHIELD_BASE = 'd="M20 13c0 5-3.5 7.5-8 8.5-4.5-1-8-3.5-8-8.5V6l8-3 8 3Z"'

# (CSS color token, inner-glyph SVG paths) per status code - red for an
# actual WAF block, amber for a soft limit, cyan (the brand accent) for a
# plain unavailability that isn't a security event at all.
_TONE_BY_CODE: dict[int, tuple[str, str]] = {
    403: ("#f87171", '<path d="m14.5 9-5 5"/><path d="m9.5 9 5 5"/>'),  # shield-x
    413: ("#fbbf24", '<path d="M12 8v4"/><path d="M12 16h.01"/>'),  # shield-alert
    429: ("#fbbf24", '<path d="M12 8v4"/><path d="M12 16h.01"/>'),  # shield-alert
    503: ("#22d3ee", ""),  # plain shield
}


def _icon(code: int, size: int) -> str:
    _, inner = _TONE_BY_CODE.get(code, ("#22d3ee", ""))
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path {_SHIELD_BASE}/>{inner}</svg>'
    )


def _page(code: int, heading: str, message: str) -> str:
    tone, _ = _TONE_BY_CODE.get(code, ("#22d3ee", ""))
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{code} {heading}</title>{_STYLE}</head>
<body style="--tone:{tone}">
  <div class="glow"></div>
  <div class="card">
    <div class="icon-badge">{_icon(code, 28)}</div>
    <h1>{heading}</h1>
    <p class="code">{code}</p>
    <p>{message}</p>
    <div class="brand">{_icon(code, 14)} Sentinel WAF</div>
  </div>
</body>
</html>
"""


ERROR_PAGE_TITLES: dict[int, str] = {
    403: "Blocked by WAF",
    413: "Payload Too Large",
    429: "Rate Limited",
    503: "Service Unavailable",
}

DEFAULT_ERROR_PAGES: dict[int, str] = {
    403: _page(403, "Blocked by WAF", "This request was blocked by the Web Application Firewall."),
    413: _page(413, "Payload Too Large", "The request you sent is larger than the server allows."),
    429: _page(429, "Rate Limited", "You've sent too many requests. Please slow down and try again shortly."),
    503: _page(503, "Service Unavailable", "The service is temporarily unavailable. Please try again later."),
}
