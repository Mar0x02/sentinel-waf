// Anti-Bot menu (Sites > per-site page, not a Sites-form checkbox) - four
// independent toggles, all funneled through this one content handler:
//
//   bot_challenge_enabled     - JS cookie challenge ("Checking your
//                                browser..."). A plain script/curl bot
//                                never runs the inline <script>, so it
//                                never gets the cookie and never reaches
//                                the real backend. Does nothing against a
//                                headless browser that actually runs JS.
//   honeypot_checkbox_enabled - modifies the challenge page: a visible
//                                "I'm not a robot" checkbox plus a
//                                CSS-hidden decoy one. A human only sees
//                                and ticks the visible one; a bot that
//                                blindly ticks every checkbox it finds
//                                trips the decoy and gets trapped.
//                                Requires bot_challenge_enabled (there's
//                                no challenge page to put it on otherwise
//                                - enforced in schemas/sites.py).
//   honeypot_path_enabled     - decoy locations for paths generic
//                                scanners/crawlers probe on virtually any
//                                host (.env, wp-login.php, ...) - see
//                                render_service.py's _HONEYPOT_PATHS. Any
//                                hit traps the source IP, same as above.
//   block_bad_user_agents     - pure nginx (no njs), see
//                                render_service.py's _bad_user_agent_directive.
//
// Trap persistence: ModSecurity v3 (libmodsecurity, used by this stack's
// nginx connector) does NOT support persistent collections the way v2
// did - confirmed by live testing (initcol/setvar/SecDataDir never wrote
// anything to disk, a second request from the same IP sailed straight
// through). So "once trapped, stay blocked" is implemented here instead,
// as a flat file this container owns - see TRAP_FILE below. This is a
// deliberate choice to keep waf-engine self-contained (no new
// waf-engine -> backend call, matching how this project is wired
// everywhere else - see CLAUDE.md) at the cost of the trap list being
// per-container (reset on waf-engine restart) and separate from the
// dashboard's own Postgres-backed IP blocklist (Access Control page) -
// a trapped IP won't show up there.
var fs = require('fs');
var crypto = require('crypto');

var CHALLENGE_TTL_SECONDS = 1800;
var TRAP_TTL_SECONDS = 86400;
var SECRET_PATH = '/etc/nginx/njs/challenge-secret';
// /etc/nginx/njs is root:root, not writable by the nginx worker process
// (which runs as uid 101/"nginx", not root) - confirmed by hitting
// "Error: Permission denied" there. /tmp is world-writable (1777) in
// this image, same place nginx's own temp paths already live.
var TRAP_FILE = '/tmp/sentinel-trapped-ips.txt';

var cachedSecret = null;
function secret() {
    // Read once per worker process, not per request - the secret file is
    // written once at container startup and never changes until restart.
    if (cachedSecret === null) {
        cachedSecret = fs.readFileSync(SECRET_PATH, 'utf8').trim();
    }
    return cachedSecret;
}

function sign(ip, expiry) {
    var h = crypto.createHmac('sha256', secret());
    h.update(ip + ':' + expiry);
    return h.digest('hex');
}

function isValidChallengeCookie(r, token) {
    if (!token) return false;
    var dot = token.indexOf('.');
    if (dot < 0) return false;
    var expiry = parseInt(token.substring(0, dot), 10);
    var sig = token.substring(dot + 1);
    if (!expiry || Date.now() / 1000 > expiry) return false;
    return sign(r.remoteAddress, expiry) === sig;
}

function now() {
    return Math.floor(Date.now() / 1000);
}

function readTrapEntries() {
    try {
        return fs.readFileSync(TRAP_FILE, 'utf8').split('\n').filter(function (l) { return l; });
    } catch (e) {
        return [];
    }
}

function isTrapped(r) {
    var t = now();
    var entries = readTrapEntries();
    for (var i = 0; i < entries.length; i++) {
        var parts = entries[i].split(':');
        if (parts[0] === r.remoteAddress && parseInt(parts[1], 10) > t) return true;
    }
    return false;
}

function recordTrap(r) {
    var t = now();
    var kept = readTrapEntries().filter(function (line) {
        var parts = line.split(':');
        // Drop this IP's old entry (replaced below with a fresh expiry)
        // and anything else already expired, so the file doesn't grow
        // without bound.
        return parts[0] !== r.remoteAddress && parseInt(parts[1], 10) > t;
    });
    kept.push(r.remoteAddress + ':' + (t + TRAP_TTL_SECONDS));
    fs.writeFileSync(TRAP_FILE, kept.join('\n') + '\n');
}

// Decoy location (render_service.py's _HONEYPOT_PATHS) - any hit here is,
// by definition, not a real visitor (nothing links to these paths), so it
// traps unconditionally. Returns a plain 404 rather than 403 so a scanner
// doesn't get a signal that it hit something special.
function trapHit(r) {
    if (!isTrapped(r)) recordTrap(r);
    r.return(404, 'Not Found');
}

function autoChallengePage(token) {
    return '<!DOCTYPE html><html><head><title>Just a moment...</title></head>' +
        '<body><p>Checking your browser before continuing...</p>' +
        '<script>document.cookie="sentinel_chal=' + token + '; path=/; max-age=' + CHALLENGE_TTL_SECONDS + '"; location.reload();</script>' +
        '</body></html>';
}

function checkboxChallengePage(token) {
    // The decoy checkbox is CSS-hidden (off-screen + opacity:0), not
    // type="hidden" - a bot that only parses raw HTML attributes (rather
    // than rendering CSS) would otherwise have an easy tell to skip it.
    return '<!DOCTYPE html><html><head><title>Just a moment...</title></head>' +
        '<body><p>Please confirm you are not a robot.</p>' +
        '<label><input type="checkbox" id="sentinel_verify"> I\'m not a robot</label><br>' +
        '<input type="checkbox" id="sentinel_decoy" tabindex="-1" autocomplete="off" ' +
        'style="position:absolute;left:-9999px;opacity:0">' +
        '<br><button type="button" onclick="sentinelSubmit()">Continue</button>' +
        '<script>function sentinelSubmit(){' +
        'if(document.getElementById("sentinel_decoy").checked){location.href="/?sentinel_decoy=1";return;}' +
        'if(!document.getElementById("sentinel_verify").checked){return;}' +
        'document.cookie="sentinel_chal=' + token + '; path=/; max-age=' + CHALLENGE_TTL_SECONDS + '";' +
        'location.reload();}</script></body></html>';
}

function check(r) {
    if (isTrapped(r)) {
        r.return(403, 'Forbidden');
        return;
    }
    if (r.variables.sentinel_bot_challenge !== '1') {
        // Only a honeypot toggle is on for this site (no JS challenge) -
        // nothing else to gate on here, go straight through.
        r.internalRedirect('@sentinel_backend');
        return;
    }
    var honeypotOn = r.variables.sentinel_honeypot_checkbox === '1';
    if (honeypotOn && r.args.sentinel_decoy) {
        recordTrap(r);
        r.return(403, 'Forbidden');
        return;
    }
    if (isValidChallengeCookie(r, r.variables.cookie_sentinel_chal)) {
        r.internalRedirect('@sentinel_backend');
        return;
    }
    var expiry = now() + CHALLENGE_TTL_SECONDS;
    var token = expiry + '.' + sign(r.remoteAddress, expiry);
    r.headersOut['Content-Type'] = 'text/html; charset=utf-8';
    r.headersOut['Cache-Control'] = 'no-store';
    r.return(200, honeypotOn ? checkboxChallengePage(token) : autoChallengePage(token));
}

export default { check, trapHit };
