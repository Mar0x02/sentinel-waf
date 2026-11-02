"""Default content for the "Base Tuning" rule set's setup file.

This is a standalone, CRS-independent anomaly-scoring scaffold - it exists
so a custom rule (Rules > Custom Rules) can use the same
"increment a score, block only once a threshold is crossed" pattern CRS
uses, without requiring any CRS package to actually be imported/enabled.
Rule IDs live in the 100000-199999 range specifically to never collide
with CRS's own reserved 900000-999999 setup-rule range, in case CRS is
imported alongside this.

Only ONE tx.* value is pre-seeded here (inbound_anomaly_score_threshold) -
everything else (severity scores, paranoia levels, per-level running
totals) is deliberately left for a custom rule's own lint warning to add
on demand (manually, or one click via the "add it" fix - see
tx_var_linter.py's _find_fix and KNOWN_DEFAULTS below), not pre-populated
here before anything actually needs it. This was a deliberate reversal
from an earlier version that pre-seeded all ~11 vars unconditionally -
changed because a fresh install had no custom rules yet to need most of
them, which isn't what "the file exists, but its content grows only as
rules require it" should look like.

Why the threshold is the one exception, kept pre-seeded no matter what:
tested a fully empty version (removing even this) against a real request,
and it does NOT fail safe. ModSecurity's `@ge` operator against an
*undefined* %{tx.inbound_anomaly_score_threshold} doesn't skip or error -
it matches an empty string as its comparison parameter, and the real
audit log entry read:

    Matched "Operator `Ge' with parameter `' against variable
    `TX:INBOUND_ANOMALY_SCORE' (Value: `0')

i.e. `0 >= ''` evaluated true - id:100960 fired and denied the request
even though nothing matched and the real score was 0. Every single
request through the WAF would have been blocked the moment this file's
plumbing was active with no threshold defined - a self-inflicted
site-wide outage, not a harmless gap. tx.inbound_anomaly_score_pl1 being
undefined, by contrast, is safe: setvar's `+=` form on a never-set var
cleanly starts from 0 (confirmed in the same test - TX:INBOUND_ANOMALY_
SCORE came out as a clean `0`, not empty/NaN), so leaving pl1 and
everything else to be added on demand doesn't share this failure mode.

Three pieces, same file (render_service.render_rules() places this file
in zzz-overrides/ - the directory that's always Included last - rather
than its own rule-set directory; see there for why):

1. id:100900 - just the one safety-critical default (see above).
2. id:100950 (aggregate pl1 into the running total) and id:100960 (the
   actual disruptive action) - confirmed against CRS's real
   REQUEST-949-BLOCKING-EVALUATION.conf that a bare scoring rule with no
   id:100960-equivalent never actually blocks anything, since individual
   detection rules only ever `pass` - only this final threshold check
   uses `deny`.

Deliberately does NOT set SecDefaultAction (confirmed necessary by
testing - an earlier version did, and nginx -t failed with
"SecDefaultActions can only be placed once per phase" the moment a real
CRS package was also enabled, since CRS's own
REQUEST-901-INITIALIZATION.conf already sets one). It isn't needed either
way: a plain `block` action with no SecDefaultAction anywhere already
resolves to ModSecurity's own built-in default, which is `pass` -
confirmed by testing a custom rule's bare `block` action with nothing
else active at all, before this file existed.
"""

# Sensible starting values for the vars a custom rule commonly needs that
# this file doesn't pre-seed - used by tx_var_linter.py's "add it" fix so
# a one-click add lands on a real CRS-convention default (critical=5,
# etc.) instead of an unhelpful "0" for every name. Any var not in here
# still gets offered with "0" as a placeholder - this table only covers
# the well-known CRS-style names, not an exhaustive list.
KNOWN_DEFAULTS: dict[str, str] = {
    "critical_anomaly_score": "5",
    "error_anomaly_score": "4",
    "warning_anomaly_score": "3",
    "notice_anomaly_score": "2",
    "outbound_anomaly_score_threshold": "4",
    "blocking_paranoia_level": "1",
    "detection_paranoia_level": "1",
    "inbound_anomaly_score_pl1": "0",
    "inbound_anomaly_score_pl2": "0",
    "inbound_anomaly_score_pl3": "0",
    "inbound_anomaly_score_pl4": "0",
    "inbound_anomaly_score": "0",
}

DEFAULT_BASE_TUNING_CONFIG = """\
# Base Tuning - Sentinel's own anomaly-scoring scaffold, independent of
# whether any OWASP CRS package is imported. A custom rule can contribute
# to tx.inbound_anomaly_score_pl1 via setvar (see the Rules page's lint
# warnings for an example - they'll offer to add whatever var a rule
# needs right here, one click or manual, your choice) and this file's own
# id:100960 below is what actually turns an accumulated score into a
# blocked request.
#
# inbound_anomaly_score_threshold is the one value pre-seeded here from
# the start - every other tunable (severity scores, paranoia levels, the
# per-level running totals) only gets added once a custom rule actually
# needs it, via that same lint warning. This is a regular setup file,
# editable and version-tracked like crs-setup.conf for an imported rule
# set either way.

SecAction \\
    "id:100900,\\
    phase:1,\\
    pass,\\
    nolog,\\
    t:none,\\
    setvar:tx.inbound_anomaly_score_threshold=5"

# Sums this transaction's paranoia-level-1 contributions into the running
# total. Rendered last (zzz-overrides) so every other rule set's phase:2
# contribution has already run by the time this adds them up. Safe even
# before any custom rule ever sets tx.inbound_anomaly_score_pl1 - setvar's
# `+=` form starts a never-set var from 0, confirmed by testing.
SecAction \\
    "id:100950,\\
    phase:2,\\
    pass,\\
    nolog,\\
    t:none,\\
    setvar:tx.inbound_anomaly_score=+%{tx.inbound_anomaly_score_pl1}"

# The actual block - without this, nothing in this file ever has a
# disruptive effect, only bookkeeping (confirmed against CRS's own
# REQUEST-949-BLOCKING-EVALUATION.conf, id:949110).
SecRule TX:INBOUND_ANOMALY_SCORE "@ge %{tx.inbound_anomaly_score_threshold}" \\
    "id:100960,\\
    phase:2,\\
    deny,\\
    t:none,\\
    msg:'Inbound Anomaly Score Exceeded (Total Score: %{TX.INBOUND_ANOMALY_SCORE})',\\
    tag:'anomaly-evaluation'"
"""
