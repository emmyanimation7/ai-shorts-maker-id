# AI Shorts Maker ID — paket Render

Aplikasi web untuk menganalisis video, mengusulkan klip, membuat narasi Bahasa Indonesia, dan merender MP4 vertikal dengan voice-over.

## Penting sebelum digunakan
- Memerlukan `GEMINI_API_KEY` agar analisis AI aktif. Buat key di Google AI Studio: https://aistudio.google.com/apikey
- Jangan pernah menaruh API key dalam file publik atau mengirimkannya ke orang lain. Tambahkan hanya di Render → Environment → Add Environment Variable (key `GEMINI_API_KEY`).
- Hosting gratis memiliki batas CPU/memori/waktu; video besar dapat gagal. File hasil di server gratis bersifat sementara, jadi unduh hasil segera. Render dapat tidur saat tidak aktif.

## Deploy dari HP
1. Ekstrak ZIP ini di iPhone menggunakan app Files.
2. Buat akun GitHub di https://github.com/signup lalu buat repository baru bernama `ai-shorts-maker-id`. Pilih Public, jangan centang README (karena paket sudah punya README).
3. Di repo baru, tekan **Add file → Upload files**, pilih semua file yang ada di dalam folder hasil ekstraksi (bukan ZIP-nya), lalu **Commit changes**.
4. Daftar/login di https://render.com/ . Pilih **New + → Web Service**. Hubungkan GitHub dan pilih repo `ai-shorts-maker-id`.
5. Pilih runtime **Docker** dan paket **Free** bila tersedia. Buat service.
6. Setelah service dibuat, buka **Environment** → **Add Environment Variable**. Isi Name `GEMINI_API_KEY`, Value dengan API key Google AI Studio. Simpan; Render akan deploy ulang.
7. Tunggu status **Live**, lalu buka URL `https://nama-service.onrender.com`. Simpan URL itu sebagai bookmark di iPhone.

## Catatan
Render free service dapat berhenti saat tidak aktif dan file lokal bisa hilang ketika restart/deploy. Gunakan video ukuran kecil dulu untuk pengujian. API key/kuota Gemini dan batas gratis Render bisa berubah.
