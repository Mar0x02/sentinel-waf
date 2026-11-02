"""Default content for the Settings page's Advanced textarea.

Every line is commented out (`#`) and shows ModSecurity's own recommended
default value - activating one is just deleting its leading `#`, same
"commented block, uncomment to activate" convention CRS itself uses in
crs-setup.conf (see crs_tuning.py / tunable_scanner.py). This is purely a
starting value for a *new* EngineSettings row (see
render_service.get_or_create_engine_settings) - once a user has saved
their own advanced_config, it's never overwritten back to this.

Only directives NOT already covered by a structured field above are
listed here - repeating one of those (SecAuditEngine,
SecAuditLogRelevantStatus, SecRequestBodyAccess, SecResponseBodyAccess,
SecRequestBodyLimit, SecResponseBodyLimit, SecResponseBodyMimeType) would
silently win over that field's value, since this file loads after it.
SecAuditLog / SecAuditLogFormat are deliberately excluded even though
they're uncovered - changing either breaks this dashboard's own log
parsing (modsec_v3_json.py expects a fixed JSON path), so they're not
something to invite someone to casually try from this textarea.
"""

DEFAULT_ADVANCED_CONFIG = """\
# Advanced ModSecurity directives - uncomment (remove the leading #) and
# adjust the value to activate. Values shown are ModSecurity's own
# recommended defaults, a safe starting point if you're not sure.

# Max size (bytes) of request bodies that don't include a file upload -
# lower than the Request body limit above, since most non-upload requests
# are far smaller than ones that attach a file.
#SecRequestBodyNoFilesLimit 131072

# What to do when the Request body limit above is exceeded: Reject
# (block the request) or ProcessPartial (inspect what fits, let the rest
# through unchecked).
#SecRequestBodyLimitAction Reject

# Max nesting depth ModSecurity will parse in a JSON request body - guards
# against deeply-nested JSON crafted to exhaust CPU/memory.
#SecRequestBodyJsonDepthLimit 512

# Max number of ARGS (query string + body parameters) allowed per
# request - guards against parameter-flooding style DoS attempts.
#SecArgumentsLimit 1000

# Max steps a PCRE regex match may take before ModSecurity aborts it -
# the main defense against ReDoS (catastrophic backtracking) in a rule's
# regex. Lower this if ModSecurity itself is using too much CPU; raise it
# if legitimate rules are getting cut off mid-match.
#SecPcreMatchLimit 100000

# Same as above, but specifically for recursive backtracking.
#SecPcreMatchLimitRecursion 100000

# What to do when the Response body limit above is exceeded:
# ProcessPartial (inspect what fits) or Reject (block the whole response).
#SecResponseBodyLimitAction ProcessPartial

# How long (seconds) a persisted collection - e.g. IP-based counters some
# rule sets use for rate-limiting style checks - is kept before expiring.
#SecCollectionTimeout 3600

# How cookies are parsed: 0 = default/strict, 1 = compatible with older
# or non-conformant cookie formats some legacy apps still send.
#SecCookieFormat 0

# Which parts of a transaction get written to each audit log entry, as a
# string of letter codes: A=header, B=request headers, C=request body,
# E=response body, F=response headers, H=audit log trailer (matched rule
# messages), I=request body minus uploaded files, J=uploaded file info,
# K=full list of every matched rule, Z=final boundary (always last).
# The value below is this project's own starting point *minus* E (response
# body) - full response bodies (e.g. whole HTML pages) bloat the audit log
# fast and usually aren't needed to see what a rule matched. Add E back in
# if you need the actual response content in the Logs page detail view.
#SecAuditLogParts ABIJDFHZ
"""
