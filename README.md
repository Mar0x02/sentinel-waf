# Sentinel WAF

Dashboard manajemen WAF berbasis **ModSecurity** - bukan WAF baru dengan
engine sendiri, tapi layer manajemen di atas ModSecurity yang bikin
pengelolaannya semudah tool WAF komersial (gaya SafeLine): rule, reverse
proxy, dan log semuanya diatur lewat dashboard web, bukan edit file
`.conf` manual atau `docker exec` ke container.

Semua state (rule set yang diimport, rule yang aktif/nonaktif, daftar site,
tujuan forward log) tersimpan di **PostgreSQL**, bukan cuma file - jadi
auditable dan gampang di-manage dari satu tempat.

## Fitur

- **Rule management berbasis database** - import OWASP CRS tinggal pilih
  dari daftar versi yang tersedia atau paste URL rule package custom.
  Setiap rule yang masuk tercatat sebagai baris di database, bisa
  diaktifkan/nonaktifkan per file rule atau per rule ID individual (lewat
  `SecRuleRemoveById`, tanpa pernah menyentuh file asli vendor).
- **Reverse proxy (Sites)** - daftarkan domain + upstream backend dari
  dashboard, langsung jadi server block nginx yang otomatis dilindungi
  oleh rule yang aktif.
- **Log forwarding** - audit log ModSecurity bisa diarahkan ke syslog
  server eksternal (SIEM, dst), selain tetap bisa dilihat langsung di
  dashboard (trend serangan, top rule yang ke-trigger, top IP penyerang).
- **Live reload otomatis** - perubahan rule atau site dari dashboard
  langsung diterapkan ke container WAF tanpa restart manual.
- **Custom error pages** - halaman HTML yang ditampilkan untuk status 403
  (diblokir WAF), 429 (rate limited), 413 (payload kebesaran), dan 503
  (service unavailable) bisa diedit langsung dari dashboard, lengkap
  dengan preview dan tombol reset ke default.
- **Login & bahasa** - dashboard terkunci di belakang login admin (password
  awal di-generate otomatis, lihat bagian Login di bawah), dan tersedia
  dalam Bahasa Indonesia atau English (tinggal toggle).

## Arsitektur

Terdiri dari 5 container terpisah (docker compose):

| Container       | Peran |
|-----------------|-------|
| `postgres`      | Menyimpan state: rule sets/files/rules, sites, log sinks |
| `backend`       | FastAPI - API dashboard, merender state DB jadi config untuk WAF |
| `frontend`      | Dashboard web (React) |
| `waf-engine`    | Jalur traffic sebenarnya: nginx + ModSecurity v3 + OWASP CRS |
| `log-forwarder` | Membaca audit log dan meneruskannya ke syslog sink yang dikonfigurasi |

`backend` dan `waf-engine` tidak saling memanggil API secara langsung -
komunikasinya lewat Docker named volume yang di-share: backend menulis
config hasil render, `waf-engine` memantau volume tersebut dan otomatis
reload nginx saat ada perubahan.

## Prasyarat

- [Docker](https://docs.docker.com/get-docker/) dan Docker Compose v2
  (sudah dites dengan Docker 29.x / Compose v5.x)
- Port `5173`, `8000`, dan `8080` tersedia di mesin kamu
- Koneksi internet (buat download image dasar + rule OWASP CRS saat import
  pertama kali)

## Instalasi

```bash
# 1. Clone repo ini
git clone https://github.com/Mar0x02/sentinel-waf.git
cd sentinel-waf

# 2. Jalankan installer - build, start semua service di background,
#    dan begitu backend siap, langsung tampilkan username + password
#    admin awal di terminal ini (gak perlu command tambahan).
./install.sh
```

`install.sh` itu cuma wrapper tipis di atas `docker compose up -d --build`
yang nunggu backend siap sebelum nampilin credential - stack-nya sendiri
tetap jalan di background seperti biasa setelah installer selesai. Kalau
mau jalanin manual tanpa installer: `docker compose up -d --build`, lalu
`docker compose logs backend | grep -A5 "admin account created"`.

Setelah itu buka:

- **Dashboard**: `http://localhost:5173`
- **Backend API**: `http://localhost:8000` (opsional, cuma kalau mau cek API langsung)
- **WAF (jalur traffic)**: `http://localhost:8080` (ini yang nantinya jadi tujuan trafik situs yang dilindungi)

## Login pertama kali

Dashboard butuh login - **tidak ada password default yang bisa ditebak**.
`install.sh` nampilin username + password admin itu langsung di terminal.
Password ini **cuma ditampilkan sekali** (gak pernah disimpan dalam bentuk
plaintext di mana pun), kira-kira begini:

```
==================================================================
  Sentinel WAF - initial admin account created
  username: admin
  password: <random, cuma muncul sekali di sini>
==================================================================
```

Login pakai username `admin` + password itu di `http://localhost:5173`.
Dashboard bakal langsung minta kamu ganti password itu ke password sendiri
sebelum bisa lanjut pakai fitur lain.

### Lupa password?

```bash
./reset-admin.sh
```

Password admin langsung di-generate ulang (random) dan ditampilkan sekali
di terminal, mirip `./install.sh`. Semua sesi login yang lagi aktif juga
otomatis ke-logout (jaga-jaga kalau reset-nya karena curiga ada yang akses
tanpa izin). Login lagi pakai password baru itu, nanti diminta ganti lagi.

## Setup pertama kali

Begitu login, dashboard masih **kosong rule** (sengaja - gak ada CRS
otomatis ter-load dari image vendor, biar semua rule yang aktif benar-benar
tercatat lewat dashboard). Langkah-langkahnya:

1. Tab **Rules** → import OWASP CRS versi terbaru dari daftar katalog
   (tinggal klik "Import").
2. Tab **Sites** → tambahkan domain + upstream backend aplikasi yang mau
   dilindungi (misal `shop.example.com` → `http://app-backend:3000`).
3. Arahkan trafik ke `http://localhost:8080` dengan header `Host` sesuai
   domain yang didaftarkan di langkah 2 (atau setup DNS/reverse proxy di
   depannya kalau mau diakses pakai domain asli).
4. Tab **Logs** / **Dashboard** buat memantau request yang di-block atau
   terdeteksi mencurigakan.
5. Tab **Settings** kalau mau meneruskan log ke syslog server eksternal
   (SIEM, dst).

## Menghentikan / membersihkan

```bash
docker compose down        # stop semua container, data tetap tersimpan
docker compose down -v     # stop + hapus semua data (rule, site, log, dst)
```

## Struktur folder

```
backend/          FastAPI app (Postgres via SQLAlchemy)
  app/adapters/     parser audit log per format WAF engine
  app/services/     importer rule package, render_service (DB -> config file)
  app/api/          HTTP routes
frontend/          Dashboard React + Vite
waf-engine/        Dockerfile custom di atas owasp/modsecurity-crs:nginx
log-forwarder/     Sidecar kecil (Python stdlib) buat forward log ke syslog
docker-compose.yml
```

## Belum tersedia (keterbatasan saat ini)

- TLS/HTTPS otomatis di Sites (HTTP-only untuk sekarang, cert manual belum ada UI-nya)
- Mode WAF (enforce/detection) masih global, belum bisa per-site
- Audit log belum di-ingest ke Postgres (dashboard baca langsung dari file log)
- Log sink baru mendukung syslog (webhook/Elasticsearch belum ada)
- Belum ada schema migration tool (Alembic) - skema dibuat otomatis saat startup
- Dukungan Apache + mod_security2 belum diimplementasikan (baru ModSecurity v3/nginx)
