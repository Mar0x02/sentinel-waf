#!/bin/sh
# Keeps the ModSecurity audit log (SecAuditLogType Serial - a single
# ever-appended file) from growing without bound, and organizes history
# into one folder per calendar day for the dashboard's Log Archive page.
#
# Layout inside the shared audit-logs volume:
#   live/audit.log                           - today's in-progress chunk,
#                                               read by the Live Log page
#                                               (backend's audit_log_dir)
#   archive/<YYYY-MM-DD>/audit-<s>_<e>.gz     - every completed chunk,
#                                               gzip'd, start/end = HHMMSS
#                                               range it covers that day
#
# A chunk is cut (gzip'd into that day's folder, live file truncated)
# whenever EITHER is true:
#   - it has grown past AUDIT_LOG_MAX_SIZE_MB (default 50) - keeps one
#     day's worth of heavy traffic from becoming one unreadable blob
#   - the day has rolled over (the live file's own mtime is no longer
#     "today") - every day's chunks are bounded to that day's 00:00:00-
#     23:59:59, per the dashboard's Log Archive design; the *last* chunk
#     of a day always ends at "235959" regardless of the actual poll
#     instant that caught it (see below)
#
# Chunks are never deleted - archiving is the point. Nothing here prunes
# the archive; add that separately if disk ever actually gets tight over
# a long deployment lifetime.
#
# copytruncate, not rename+recreate: ModSecurity holds live/audit.log open
# for writing for the container's whole lifetime and there's no reopen
# signal wired up for it (unlike nginx's own logs, which `nginx -s reopen`
# handles) - renaming it out from under that open fd would mean every
# future write keeps landing in the renamed file forever. Truncating in
# place is safe because the writer keeps appending at its current fd
# offset into the (now short) file.
#
# No persisted "what day is open" state file needed: which day a pending
# chunk belongs to is read straight off the live file's own mtime (the
# calendar date ModSecurity last actually wrote to it), not wall-clock
# "today" at poll time - so a poll that notices the rollover up to
# POLL_SECONDS late still files the leftover data under the day it was
# really written on, not the new day. Same reasoning for the start/end
# chain within a day: it's read back from the newest existing archive
# filename in that day's folder (or "000000" - midnight - if that day has
# no chunks yet), no separate state file.
#
# backend/app/adapters/modsec_v3_json.py's parse_dir() only ever points at
# live/, and log-forwarder/forwarder.py only ever tails live/audit.log -
# neither needs to know archive/ exists at all, so the archive growing
# forever doesn't cost either of them anything (see CLAUDE.md).
set -eu

LIVE_LOG=/var/log/modsecurity/audit/live/audit.log
LIVE_DIR=$(dirname "$LIVE_LOG")
ARCHIVE_ROOT=/var/log/modsecurity/audit/archive
MAX_SIZE_BYTES=$(( ${AUDIT_LOG_MAX_SIZE_MB:-50} * 1024 * 1024 ))

# Must exist before nginx/ModSecurity starts (docker-entrypoint.d scripts
# all run before the final `exec nginx`) - ModSecurity can't open
# live/audit.log for writing on a fresh volume if live/ doesn't exist yet.
mkdir -p "$LIVE_DIR" "$ARCHIVE_ROOT"

(
  set +e
  while true; do
    sleep 60

    if [ -f "$LIVE_LOG" ]; then
      size=$(stat -c%s "$LIVE_LOG" 2>/dev/null || echo 0)

      if [ "$size" -gt 0 ]; then
        mtime_epoch=$(stat -c%Y "$LIVE_LOG" 2>/dev/null || echo 0)
        mtime_date=$(date -d "@$mtime_epoch" +%Y-%m-%d 2>/dev/null || date +%Y-%m-%d)
        today=$(date +%Y-%m-%d)

        do_cut=0
        end_label=$(date +%H%M%S)
        if [ "$size" -gt "$MAX_SIZE_BYTES" ]; then
          do_cut=1
        fi
        if [ "$mtime_date" != "$today" ]; then
          do_cut=1
          end_label=235959
        fi

        if [ "$do_cut" -eq 1 ]; then
          day_dir="$ARCHIVE_ROOT/$mtime_date"
          mkdir -p "$day_dir"

          latest=$(find "$day_dir" -maxdepth 1 -name 'audit-*_*.gz' -print 2>/dev/null | sort | tail -n1)
          start_label=000000
          if [ -n "$latest" ]; then
            parsed=$(basename "$latest" .gz | sed -n 's/.*_\([0-9]\{6\}\)$/\1/p')
            [ -n "$parsed" ] && start_label=$parsed
          fi

          archive="$day_dir/audit-${start_label}_${end_label}.gz"
          if gzip -c "$LIVE_LOG" > "$archive"; then
            : > "$LIVE_LOG"
            echo "$(date -Iseconds) archived $LIVE_LOG (${size} bytes) -> $archive" >> /tmp/audit-log-rotate.log
          fi
        fi
      fi
    fi
  done
) &
