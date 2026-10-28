PANDUAN UPDATE TAMPILAN ENKEI MONITORING

Isi paket:
- templates/dashboard.html
- static/css/style.css
- static/js/dashboard.js

CARA MEMASANG (Windows / VS Code)
1. Hentikan Flask di terminal dengan menekan Ctrl+C.
2. Buat salinan cadangan dari tiga file lama tersebut.
3. Ekstrak ZIP ini.
4. Salin folder templates dan static dari paket ini ke folder proyek C:\monitoring-server.
   Pastikan file masuk ke lokasi berikut:
   C:\monitoring-server\templates\dashboard.html
   C:\monitoring-server\static\css\style.css
   C:\monitoring-server\static\js\dashboard.js
5. Jika Windows bertanya apakah file lama akan diganti, pilih Replace untuk tiga file di atas saja.
6. Jangan mengganti app.py, config.py, server_monitoring.sql, atau database.
7. Jalankan kembali Flask menggunakan perintah yang biasa dipakai untuk proyek ini.
8. Buka http://127.0.0.1:5000/dashboard
9. Tekan Ctrl+F5 untuk memuat CSS/JavaScript baru.

CATATAN
- Tampilan baru menggunakan API yang sudah ada: /api/servers dan /api/monitoring.
- Data grafik, CPU, RAM, disk, server, dan backup tetap dibaca dari database melalui API.
- Status ONLINE/OFFLINE tidak dibuat-buat; dashboard mengikuti status API.
- Chart.js dan Google Fonts dimuat melalui CDN sehingga perlu koneksi internet untuk grafik/font eksternal.
