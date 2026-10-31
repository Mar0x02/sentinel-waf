"""Built-in fallback content for the error pages feature.

The set of status codes is fixed deliberately - the nginx `error_page`
directives for these codes are baked into the waf-engine image
(waf-engine/error-pages.conf), not rendered dynamically, so adding a new
code here alone does nothing without also adding it there and rebuilding
the image. See CLAUDE.md.
"""

_STYLE = """
<style>
  body { font-family: system-ui, -apple-system, sans-serif; background:#0d0d0d; color:#f0efec;
         display:flex; align-items:center; justify-content:center; min-height:100vh; margin:0; }
  .box { text-align:center; padding:40px; }
  h1 { font-size:64px; margin:0 0 8px; color:#d03b3b; }
  p { color:#c3c2b7; font-size:16px; }
  .brand { margin-top:24px; font-size:13px; color:#898781; letter-spacing:0.05em; text-transform:uppercase; }
</style>
"""


def _page(code: int, heading: str, message: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{code} {heading}</title>{_STYLE}</head>
<body>
  <div class="box">
    <h1>{code}</h1>
    <p>{message}</p>
    <div class="brand">Sentinel WAF</div>
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
    403: _page(403, "Forbidden", "This request was blocked by the Web Application Firewall."),
    413: _page(413, "Payload Too Large", "The request you sent is larger than the server allows."),
    429: _page(429, "Too Many Requests", "You've sent too many requests. Please slow down and try again shortly."),
    503: _page(503, "Service Unavailable", "The service is temporarily unavailable. Please try again later."),
}
