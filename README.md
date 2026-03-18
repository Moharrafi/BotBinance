# 🤖 AG-FUTUREBOT v1.2 (Premium Scaling)
### *Advanced Binance Futures Auto-Trading Engine with Real-Time Analytics*

![AG-FUTUREBOT Header](https://raw.githubusercontent.com/username/project/main/header.png) *(Note: Placeholder for visualization)*

---

## 🌟 Deskripsi Proyek
**AG-FUTUREBOT** adalah sistem perdagangan otomatis canggih untuk pasar *Binance Futures (USDT-M)*. Dirancang untuk stabilitas dan efisiensi, bot ini menggabungkan analisis teknikal *multi-timeframe*, manajemen risiko dinamis, dan sistem *scaling* modal otomatis untuk memaksimalkan peluang keuntungan sambil meminimalkan eksposur risiko.

Bot ini dibangun menggunakan **Python** dan **CCXT**, menyediakan dashboard interaktif yang rapi langsung di terminal Anda dengan dukungan untuk koin-koin berpresisi tinggi (micin) secara dinamis.

---

## 🚀 Fitur Unggulan

### 1. 🎯 Strategi Trading Sniper (V2 - Institutional Grade)
*   **EMA 9 & 21 Crossover:** Kombinasi standar profesional untuk akurasi momentum yang lebih stabil dibanding 7/14.
*   **EMA 50 (The Pulse):** Filter tren menengah pada timeframe eksekusi; LONG hanya jika harga di atas EMA 50, SHORT jika di bawah.
*   **RSI (Relative Strength Index) Guard:** Mencegah entry di area *overbought* (>70) untuk Long atau *oversold* (<30) untuk Short.
*   **Macro Trend Filter:** Filter utama (EMA 200 di TF 1h) untuk memastikan koin berjalan searah dengan tren besar global.
*   **Momentum & Volume Guard:** Keharusan volatilitas (`ADX > 20`) dan volume spike minimal 60% dari rata-rata volume sebelumnya.

### 2. 🛡️ Manajemen Risiko Berlapis (Premium Scaling)
*   **Triple-Layer Take Profit (TP):**
    *   **TP1:** Tutup 33% posisi & pindahkan Stop Loss ke *Break-Even* (Aman otomatis).
    *   **TP2:** Tutup 33% posisi lainnya untuk mengamankan profit tengah.
    *   **TP3:** Target maksimal berdasarkan ATR (*Average True Range*).
*   **Dynamic Trailing Stop Loss (TSL):** Fitur 💎 (Berlian) yang secara otomatis "membuntuti" harga saat profit mencapai 20%, memastikan keuntungan tidak hilang saat pasar berbalik arah.
*   **Auto-Scale Margin (Compound Interest):** Menyesuaikan ukuran posisi berdasarkan % saldo bebas terkini secara otomatis (berkembang bersama saldo Anda).

### 3. 🖥️ Ultimate Dashboard & Scanner
*   **Dynamic UI Rendering:** Tampilan board yang otomatis melebar sesuai panjang nama koin/presisi harga (Anti-Offside).
*   **Global Scanner:** Memantau hingga 25 koin teratas (*Top Gainers, Losers, atau Mixed*) sekaligus secara *real-time*.
*   **Smart Price Formatter:** Mendukung koin dengan banyak koma (hingga 8 desimal) tanpa merusak tampilan UI.

---

## 🔒 Keamanan & Perlindungan
Keamanan modal Anda adalah prioritas utama:
*   **DRY RUN (Simulasi):** Mode simulasi penuh untuk menguji strategi tanpa menggunakan uang sungguhan.
*   **Isolated Margin:** Default menggunakan mode *Isolated* untuk mencegah likuidasi menyebar ke seluruh saldo dompet.
*   **Leverage Guard:** Penyesuaian leverage otomatis jika Binance menolak angka tertentu (misal: otomatis turun ke 10x jika 20x ditolak).
*   **Emergency Stop:** Tombol darurat (tekan '0') untuk segera menutup semua posisi aktif dan membatalkan semua order di server.

---

## 🛠️ Persyaratan Sistem & Instalasi

### 📋 Prasyarat
*   Python 3.8 atau lebih tinggi
*   Binance API Key (dengan izin: Read & Futures)
*   Virtual Environment (Disarankan)

### ⚙️ Instalasi
1.  Kloning atau unduh folder project ini.
2.  Buka terminal di direktori project.
3.  Install dependensi yang diperlukan:
    ```bash
    pip install ccxt pandas ta-lib
    ```
4.  Buka file `future_bot.py` dan masukkan API Key Anda:
    ```python
    API_KEY = "MASUKKAN_API_KEY_ANDA"
    SECRET   = "MASUKKAN_SECRET_KEY_ANDA"
    ```

---

## 🎮 Cara Menjalankan

Jalankan bot dengan perintah:
```bash
python future_bot.py
```

### Navigasi Menu:
*   **[1] Global Scanner:** Bot akan mencari koin terbaik secara mandiri dan langsung melakukan trading otomatis.
*   **[2] Manual Trade:** Masukkan nama koin pilihan Anda sendiri (contoh: BTC, ETH) untuk dianalisa dan dieksekusi.
*   **[3] Top Movers:** Lihat pergerakan koin dengan volume dan perubahan harga tertinggi saat ini.
*   **[4] Trade History:** Lihat rekam jejak PnL Anda secara detail.
*   **[5] Exit:** Keluar dari program dengan aman.

---

## 📜 Logika Visual (Indikator Dashboard)
*   🛡️ **Perisai:** Fitur Break-Even aktif (Stop Loss sudah di harga masuk).
*   💎 **Berlian:** Trailing Stop Loss aktif (Profit sedang dikawal).
*   ✅ **Centang:** Target TP1 atau TP2 sudah berhasil dicapai.
*   🚀 **Roket:** Target TP3 tercapai secara maksimal.

---

## ⚠️ Disclaimer
**Trading Cryptocurrency membawa risiko tinggi.** Bot ini adalah alat bantu keputusan dan pengelolaan posisi. Hasil masa lalu tidak menjamin kinerja masa depan. Gunakan modal yang siap Anda lepaskan (*Risk Capital*). Penulis tidak bertanggung jawab atas kerugian finansial yang timbul dari penggunaan software ini.

---
*Dibuat dengan ❤️ oleh AG-FutureBot Development Team.*
