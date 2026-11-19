# StickerDrop — audit teknis dan Patch 1

Tanggal audit: 19 November 2026  
Basis audit: source ZIP yang diberikan, tiga screenshot aplikasi, dokumentasi resmi ScrapeCreators dan TikTok yang diperiksa pada tanggal audit.

## Ringkasan

StickerDrop belum siap disebut stabil untuk rilis publik. Beberapa gejala pada screenshot bukan semata-mata karena provider scraper; ada fallback buatan di backend dan Flutter yang mengubah kegagalan menjadi hasil demo. Patch 1 menghapus perilaku tersebut dan memperbaiki beberapa bug penyimpanan serta ekspor.

Patch ini adalah **source patch**. Ini belum merupakan APK yang sudah dibangun dan diuji pada perangkat Android.

## Temuan yang terkonfirmasi

1. `backend/main.py` memiliki fallback sintetis. Ketika komentar tidak ditemukan, backend membuat metadata komentar, username, ID stiker, dan URL media demo `127.0.0.1` lalu mengembalikan respons seolah ekstraksi berhasil.
2. `client/lib/features/extraction/services/extraction_service.dart` memiliki fallback kedua. Jika URL media asli gagal diunduh, aplikasi meminta file demo `prabowo_animated.awebp` lalu mengembalikan bytes tersebut sebagai stiker hasil ekstraksi.
3. Preview di Android mencoba memuat URL `127.0.0.1`. Alamat loopback pada ponsel menunjuk ke ponsel itu sendiri, bukan backend cloud, sehingga preview demo tidak dapat dimuat.
4. `client/lib/ui/screens/input_screen.dart` sebelumnya menganggap semua record baru sebagai duplikat melalui perbandingan ID setelah insert: `saved.id != model.id`. ID baru sudah terisi setelah SQLite insert, sedangkan `model.id` masih null.
5. Dedup media SHA-256 memang dapat menganggap dua stiker sama bila bytes-nya benar-benar identik. Karena fallback demo mengembalikan bytes sama untuk link berbeda, deduplikasi ini menghasilkan false positive pada alur yang terlihat pengguna.
6. Deduplikasi lokal baru dilakukan ketika pengguna menyimpan hasil, setelah permintaan ekstraksi ke provider selesai. Karena itu, ekstraksi ulang untuk komentar yang sudah ada masih dapat memakan kredit. Ini butuh preflight resolver/cache pada patch berikutnya.
7. Provider key ScrapeCreators tertulis langsung di source. Key harus dianggap terekspos dan dirotasi/revoke jika masih aktif. Patch menghapus literal tersebut; key sekarang harus disediakan sebagai secret environment.
8. Request publik sebelumnya bisa mengirim `provider=mock`, sehingga klien dapat meminta fixture demo. Provider sekarang dipilih dari environment server; request yang membawa field provider ditolak.
9. Kode mengirim parameter `count=50` ke endpoint Comments, padahal parameter yang didokumentasikan saat audit adalah `url`, `trim`, dan `cursor`.
10. Kode sebelumnya meminta endpoint replies menggunakan ID komentar target seolah-olah ID tersebut adalah ID komentar induk. Dokumentasi provider mensyaratkan `comment_id` untuk endpoint replies berupa `cid` komentar induk yang berasal dari endpoint Comments.
11. Sebelumnya empat pencarian parent replies dijalankan paralel. Jika hasil pertama sudah menemukan target, permintaan lain tetap telanjur dikirim. Patch menjalankannya berurutan dan berhenti saat target ditemukan.
12. Klasifikasi animated sebelumnya dapat memberi ekstensi `.awebp` pada URL static ketika tipe sticker menyebut animated tetapi `animated_url` tidak dikembalikan. Patch memakai URL animated hanya jika provider benar-benar memberikannya.
13. Splash Android memakai `launch_logo.png` yang memuat logo dan teks sebagai satu gambar bitmap. Di sisi Flutter, `BrandLoadingView` sebenarnya sudah menggunakan widget `Text`; teks raster pada screenshot berasal dari bitmap splash native Android.
14. WhatsApp export sebelumnya menandai record `EXPORTED` sebelum hasil intent native diketahui. Native Android juga menganggap `RESULT_CANCELED` sebagai sukses. Patch memindahkan status sukses setelah `RESULT_OK` dan memisahkan kasus pembatalan dari WhatsApp yang tidak terpasang.

## Perubahan di Patch 1

- Menghapus fallback metadata sintetis dari backend.
- Menghapus fallback pengunduhan demo dari Flutter.
- Menghapus endpoint demo media dari backend produksi.
- Mengunci pemilihan provider pada konfigurasi environment server, bukan request mobile.
- Menghapus API key tertanam dari source dan mewajibkan `SCRAPECREATORS_API_KEY`.
- Menghapus parameter Comments `count` yang tidak tercantum di dokumentasi provider.
- Menghapus request replies yang salah sasaran, mengurutkan pencarian parent secara sequential, dan berhenti saat target ditemukan.
- Memperbaiki deteksi duplikat agar melihat record existing berdasarkan `comment_id` dan SHA-256 sebelum insert.
- Memeriksa URL media dan header WebP sebelum bytes disimpan.
- Memperbaiki klasifikasi static/animated ketika URL animated tidak tersedia.
- Menandai pack `EXPORTED` hanya setelah intent WhatsApp sukses; file sumber kosong/hilang membuat ekspor gagal dengan jelas.
- Mengubah status hasil intent Android agar pembatalan bukan sukses.
- Mengganti logo, launcher icon, dan splash bitmap dengan ikon minimalis pastel. Splash native kini hanya menampilkan ikon; wordmark dan tagline tetap menggunakan Flutter `Text` sehingga dirender sebagai teks, bukan gambar.
- Menambah tes untuk komentar yang tidak ditemukan, provider override publik, dan media animated yang kehilangan URL animasinya.

## Kredit provider: apa yang masih berbiaya

Dokumentasi ScrapeCreators saat audit menyatakan halaman Comments yang berisi komentar menghabiskan 1 kredit per halaman, sedangkan halaman kosong 0 kredit. Endpoint Comment Replies menghabiskan 1 kredit per request. Backend masih dapat memeriksa maksimum lima halaman komentar dan hingga empat parent thread jika target tidak ditemukan di komentar utama/preview. Dengan demikian, kegagalan tertentu masih dapat menghabiskan beberapa kredit. Patch 1 menghapus satu request replies yang tidak tepat dan menghindari fan-out paralel, tetapi **belum menghapus biaya pencarian provider**.

Deduplikasi saat ini berada di SQLite lokal pada perangkat. Untuk menghindari biaya saat pengguna mengekstrak ulang komentar yang sudah ada, langkah berikutnya adalah endpoint resolver murah tanpa provider + local pre-check, serta cache backend untuk `comment_id`, halaman komentar, dan bytes media.

## Bisa membangun scraper sendiri?

Bisa membangun sendiri sebagian besar sistem StickerDrop: link resolver, normalisasi data, validasi media, cache, penyimpanan, SHA-256 deduplication, pack builder, dan WhatsApp export.

Bagian yang tidak dapat dijamin oleh kode milik kita saja adalah pengambilan komentar publik TikTok dan `cmt_sticker_struct` dari platform. Dokumentasi Research API resmi yang diperiksa hanya mencantumkan metadata komentar seperti ID, teks, video ID, reply count, parent ID, likes, dan waktu; tidak mencantumkan objek sticker media. Scope-nya `research.data.basic`, akses perlu persetujuan, dan FAQ menyatakan creator, advertiser, atau commercial user tidak memenuhi syarat Research Tools. Karena itu, API resmi tersebut bukan pengganti langsung ScrapeCreators bagi aplikasi StickerDrop komersial.

Scraper mandiri yang mengandalkan endpoint internal tidak resmi juga bukan solusi “gratis dan pasti stabil”: struktur internal bisa berubah, akses bisa dibatasi, serta perlu memperhatikan ketentuan platform dan hak atas media. TikTok Developer Terms global mensyaratkan penggunaan layanan developer sesuai dokumentasi dan membatasi penggunaan komersial/tidak sah tanpa persetujuan tertulis. Sementara itu, larangan scrape yang eksplisit pada Terms of Service yang berhasil diverifikasi saat audit berasal dari perjanjian wilayah Amerika Serikat, jadi tidak boleh dianggap otomatis sebagai teks yang sama untuk akun Indonesia. Jangan mengatasi CAPTCHA, login gate, atau WAF dengan bypass/proxy rotation tanpa otorisasi. Untuk jalur komersial yang aman, perlu persetujuan/akses yang sesuai atau penyedia data yang memang memberi lisensi dan dukungan penggunaan tersebut.

## Hal yang belum selesai / butuh Patch 2

1. **Resolver preflight dan cache:** cek `comment_id` di library sebelum panggilan provider; simpan cache hasil serta media bytes agar ekstraksi berulang tidak membayar lagi.
2. **Reply pagination dan pencarian lebih lengkap:** kode aktif masih membatasi kandidat parent ke empat dan hanya meminta satu halaman replies per parent. Target reply di thread yang lebih dalam dapat terlewat. Perlu anggaran request yang eksplisit, pagination, dan cache agar akurasi naik tanpa panggilan tak terkendali.
3. **Rate limit/authentication:** endpoint backend masih belum memiliki sistem kuota pengguna/rate-limit lintas instance. Karena endpoint publik dapat memicu provider berbayar, ini harus ditutup sebelum aplikasi disebarkan luas.
4. **Media validation end-to-end:** Flutter sekarang memeriksa RIFF/WEBP header; validasi dimensi 512×512, batas ukuran, frame count dan batas format WhatsApp belum dijalankan di alur backend aktif.
5. **WhatsApp QA:** perlu diuji pada Android fisik dengan WhatsApp dan WhatsApp Business, pack static/animated, file hilang, import dibatalkan, dan import berhasil.
6. **Release signing:** `client/android/app/build.gradle.kts` masih menggunakan debug signing untuk build release. Ini perlu diganti dengan release keystore sebelum distribusi produksi/Play Store.
7. **Deployment alignment:** `client/lib/core/constants/api_constants.dart` menunjuk ke Railway, sedangkan `render.yaml` mendefinisikan layanan Render. Pastikan Railway adalah deployment aktif dan environment di sana berisi secret yang benar; `render.yaml` tidak otomatis mengatur Railway.

## Cara deploy backend setelah rotasi key

Di environment Railway yang menjadi target aplikasi, atur:

```env
EXTRACTION_PROVIDER=scrapecreators
SCRAPECREATORS_API_KEY=<NEW_SECRET_FROM_PROVIDER>
SCRAPECREATORS_BASE_URL=https://api.scrapecreators.com
```

Jangan menaruh key di Dart/Flutter, asset, `.env` yang di-commit, atau GitHub Actions log. Revoke/rotate key lama terlebih dahulu. Setelah backend deploy, rebuild APK dari source Flutter yang sudah dipatch.

## Validasi yang dilakukan

- `python -m compileall -q backend src tests`: berhasil.
- `python scripts/run_tests.py`: **37 tes lulus, 0 gagal, 0 error**.
- Flutter/Dart analyzer dan Android Gradle build: tidak dijalankan karena Flutter/Dart SDK tidak tersedia di lingkungan audit ini.
- ScrapeCreators live test: tidak dijalankan karena tidak ada credential live yang diberikan.
- WhatsApp intent/content-provider runtime test: tidak dijalankan karena membutuhkan APK hasil build dan perangkat Android dengan WhatsApp.

## Rujukan resmi yang digunakan

- ScrapeCreators TikTok Comments: https://docs.scrapecreators.com/v1/tiktok/video/comments/
- ScrapeCreators TikTok Comment Replies: https://docs.scrapecreators.com/v1/tiktok/video/comment/replies/
- TikTok Research API Query Video Comments: https://developers.tiktok.com/docs/en/research-api-specs-query-video-comments
- TikTok Research API FAQ: https://developers.tiktok.com/docs/en/research-api-faq/
- TikTok Developer Terms of Service (global): https://t.tiktok.com/legal/page/global/tik-tok-developer-terms-of-service/en
- TikTok US Terms of Service (catatan: perjanjian wilayah AS, bukan pengganti pemeriksaan terms Indonesia): https://t.tiktok.com/legal/page/us/terms-of-service/en?lang=en
