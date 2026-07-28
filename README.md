# 🤖 AI Trading Bot Polymarket (Gemini 3.6 Flash Engine)

Trading bot otomatis untuk Polymarket menggunakan **Python**, **Gemini 3.6 Flash Engine** (`google-genai`), **Cloudflare Worker** (KV Store Emergency Switch), **Frontend Control Center Dashboard**, dan **GitHub Actions** (Jadwal otomatis 5 menit).

---

## 📁 Struktur Proyek

```text
├── .github/
│   └── workflows/
│       └── bot_cron.yml          # Automation GitHub Actions (Jadwal setiap 5 menit)
├── backend/
│   ├── main_bot.py               # Engine utama bot Python (Gamma API, Gemini AI, CSV logging)
│   └── requirements.txt          # Dependensi Python
├── cloudflare_worker/
│   └── worker.js                 # API Switch Status (RUNNING / STOPPED) terhubung ke Cloudflare KV
├── frontend/
│   ├── index.html                # Control Center Dashboard UI (Tailwind CSS)
│   └── app.js                    # Logic frontend & visualizer log CSV
├── catatan_simulasi_polymarket.csv # Catatan hasil simulasi & transaksi trading
└── README.md                     # Panduan setup & deployment
```

---

## 🚀 Perintah Push Kode ke GitHub

Jalankan perintah berikut pada Terminal Antigravity / Command Prompt / Git Bash untuk mengunggah proyek ini ke repositori GitHub milikmu:

```bash
# 1. Inisialisasi Git (jika belum)
git init

# 2. Tambahkan semua file baru
git add .

# 3. Commit file
git commit -m "Setup lengkap Bot Polymarket Gemini 3.6 Flash + Cloudflare Control Center (5-min Cron)"

# 4. Hubungkan ke repositori GitHub milikmu (Ganti URL dengan repositori kamu)
git remote add origin https://github.com/USERNAME_KAMU/NAMA_REPO_KAMU.git

# 5. Push ke branch utama
git branch -M main
git push -u origin main
```

---

## 🔑 Konfigurasi Rahasia (GitHub Secrets)

Buka repositori GitHub milikmu di browser, lalu masuk ke:
`Settings` ➔ `Secrets and variables` ➔ `Actions` ➔ `New repository secret`

Masukkan 3 variabel berikut:

| Nama Secret | Deskripsi |
|---|---|
| `GEMINI_API_KEY` | API Key dari Google AI Studio ([aistudio.google.com](https://aistudio.google.com)) |
| `PRIVATE_KEY_BURNER` | Private Key Ethereum / Polygon dari MetaMask Burner Wallet kamu |
| `CLOUDFLARE_KV_URL` | Endpoint Cloudflare Worker status (contoh: `https://bot-control.subdomain.workers.dev/status`) |

---

## ⚡ Setup Cloudflare Worker & KV Store

1. Buat **Worker** baru di dashboard Cloudflare.
2. Salin kode dari `cloudflare_worker/worker.js` ke editor Cloudflare Worker.
3. Buat **KV Namespace** bernama `BOT_KV`.
4. Hubungkan Binding KV Namespace di menu **Settings** ➔ **Variables** ➔ **KV Namespace Bindings**:
   - Variable name: `BOT_KV`
   - KV namespace: (pilih namespace yang baru dibuat)
5. Deploy Worker.

---

## 📊 Dashboard Control Center

Buka `frontend/index.html` langsung di browser atau host menggunakan GitHub Pages / Netlify / Vercel.
- Masukkan URL Cloudflare Worker milikmu di kolom input.
- Tekan **🟢 START BOT** untuk mengaktifkan bot.
- Tekan **🔴 EMERGENCY STOP** untuk mematikan bot secara instan dari mana saja.
