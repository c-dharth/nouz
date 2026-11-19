#!/usr/bin/env bash
# Runs the migrations and the policy tests against a throwaway local Postgres. Nothing here touches Supabase.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; ROOT="$(dirname "$HERE")"
BIN="$(ls -d /usr/lib/postgresql/*/bin 2>/dev/null | tail -1)"; [ -n "$BIN" ] || BIN="$(dirname "$(command -v initdb)")"
D="$(mktemp -d /tmp/vouzpg.XXXXXX)"; PORT=54329
AS=""; if [ "$(id -u)" = "0" ]; then chown postgres "$D"; chmod 755 "$D"; AS="runuser -u postgres --"; fi
cp "$HERE"/*.sql "$ROOT"/migrations/*.sql "$D"/ && chmod -R a+rX "$D"
$AS "$BIN/initdb" -D "$D/data" -U postgres -A trust >/dev/null
$AS "$BIN/pg_ctl" -D "$D/data" -o "-p $PORT -k $D -c listen_addresses=''" -l "$D/log" -w start >/dev/null
trap '$AS "$BIN/pg_ctl" -D "$D/data" -m immediate stop >/dev/null 2>&1; rm -rf "$D"' EXIT
P="$AS $BIN/psql -h $D -p $PORT -U postgres -v ON_ERROR_STOP=1 -q -X"
$P -c "create database vouz" postgres
for f in 00_supabase_stub.sql 0001_vouz_core.sql 0002_vouz_social.sql 05_seed_legacy.sql 0003_couple_poly_experiences.sql 06_legacy_check.sql 0004_rewards.sql 0005_feed.sql 10_policies.sql 20_rewards.sql 30_feed.sql; do $P -f "$D/$f" vouz >/dev/null; done
$P -At -c "select case when ok then 'PASS ' else 'FAIL ' end || label from test.results order by n" vouz
$P -At -c "select count(*) filter (where ok) || '/' || count(*) || ' passed' from test.results" vouz
[ "$($P -At -c "select count(*) from test.results where not ok" vouz)" = "0" ]
