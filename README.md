# Sentinel WAF

Dashboard buat ngelola WAF yang pakai **ModSecurity** sebagai engine - bukan
WAF baru, ini layer manajemen di atasnya. Arsitekturnya ala SafeLine:
`docker compose up` sekali, lalu semuanya (rule, reverse proxy, log) dikelola
dari dashboard - gak perlu `docker exec` atau edit `.conf` manual buat
pemakaian sehari-hari.

Lihat [CLAUDE.md](./CLAUDE.md) buat detail arsitektur, keputusan desain, dan
batasan yang disengaja.

## Fitur

- **Rule management, data-driven dari Postgres** - import OWASP CRS tinggal
  pilih dari daftar versi atau paste URL rule package custom. Setiap rule
  yang masuk terdaftar sebagai baris di DB, bisa diaktif/nonaktifkan per
  file atau per rule ID individual (lewat `SecRuleRemoveById`, tanpa
  nyentuh file vendor).
- **Reverse proxy (Sites)** - atur domain + upstream backend dari dashboard,
  langsung jadi server block nginx yang dilindungi ModSecurity+rule aktif.
- **Log forwarding** - audit log ModSecurity bisa diarahkan ke syslog
  server eksternal (SIEM dst), selain tetap bisa dilihat di dashboard.
- **Live reload otomatis** - ubah rule/site dari dashboard langsung
  ke-apply ke container WAF tanpa restart manual (lewat file watcher di
  container WAF, bukan Docker socket).

## Arsitektur (5 container terpisah)

```
postgres        - state: rule sets/files/rules, sites, log sinks
backend         - FastAPI, API dashboard, render config ke shared volume
frontend        - React dashboard
waf-engine      - "jalur" traffic beneran: nginx + ModSecurity v3 + CRS
log-forwarder   - tail audit log, forward ke syslog sink yang dikonfigurasi
```

Backend dan waf-engine **tidak** saling panggil API langsung - satu-satunya
hubungan adalah 3 shared Docker named volume (rules, sites, log-sink
config) yang backend tulis dan waf-engine/log-forwarder baca. Lihat
CLAUDE.md untuk alasan kenapa ini harus named volume, bukan bind-mount host.

## Jalanin

```
docker compose up --build
```

- Dashboard: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- WAF (traffic masuk sini): `http://localhost:8080`

Begitu jalan, dashboard masih **kosong rule** (gak ada CRS otomatis ter-load
dari image vendor - itu disengaja, lihat CLAUDE.md). Langkah pertama:

1. Buka `http://localhost:5173` → tab **Rules** → import OWASP CRS versi
   terbaru dari daftar katalog (sekali klik).
2. Tab **Sites** → tambah domain + upstream backend yang mau dilindungi.
3. Arahkan traffic ke `http://localhost:8080` dengan `Host` header sesuai
   domain yang didaftarkan di langkah 2 (atau setup DNS/reverse proxy di
   depannya kalau mau diakses pakai domain asli).
4. Tab **Logs**/**Dashboard** buat liat request yang ke-block.
5. Tab **Settings** kalau mau forward log ke syslog server eksternal.

## Struktur folder

```
backend/          FastAPI app (Postgres via SQLAlchemy)
  app/adapters/     audit log parser per format WAF engine
  app/services/     importer (download+parse rule package), render_service
  app/api/          HTTP routes
frontend/          React + Vite dashboard
waf-engine/        Dockerfile custom di atas owasp/modsecurity-crs:nginx
log-forwarder/     sidecar kecil (stdlib Python) buat forward log ke syslog
docker-compose.yml
CLAUDE.md          arsitektur, keputusan desain, batasan - baca ini duluan
```

## Belum ada (sengaja, lihat CLAUDE.md untuk detail)

- TLS/HTTPS otomatis di Sites (HTTP-only untuk sekarang)
- Mode WAF (enforce/detection) per-site - saat ini global
- Audit log gak di-ingest ke Postgres (tetap baca dari file)
- Log sink selain syslog (webhook/Elasticsearch)
- Schema migration (Alembic) - masih `create_all` di startup
- Dukungan Apache + mod_security2 (interface adapter sudah siap)
