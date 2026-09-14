---
name: doc-report-master
description: >
  Unified Master Skill for creating world-class documents: academic research
  reports (Stanford STORM + GPT Researcher standards), Indonesian formal reports
  (Kemendikbudristek/BRIN format), and journalistic opinion articles (Kompas/Tempo
  op-ed standard). When this skill is active, every document you produce is
  automatically structured, cited, and formatted to international or national
  professional standards.
---

# 📝 DOC-REPORT-MASTER SKILL

## 1. Kapan Skill Ini Aktif
Skill ini aktif secara otomatis ketika user meminta:
- Membuat laporan proyek, laporan penelitian, atau executive summary
- Menulis artikel opini, kolom editorial, atau essay analitis
- Menyusun dokumen formal berstandar nasional (Kemendikbudristek, BRIN, SNI)
- Membuat dokumen berstandar internasional (IEEE, APA, IMRaD, ACM, Harvard)
- Menulis makalah, proposal, white paper, atau studi kasus
- Membuat konten yang perlu disimpan sebagai file `.docx`, `.md`, atau `.pdf`

---

## 2. STANDAR A — Laporan Akademik & Penelitian (Stanford STORM + GPT Researcher)

### Proses yang Wajib Diikuti:
1. **Multi-Perspective Research Phase** (Gaya Stanford STORM):
   - Identifikasi minimal 3 sudut pandang berbeda sebelum menulis (Pro / Kontra / Perspektif Alternatif).
   - Jika tools tersedia, gunakan `fetch_url` atau `web_search` untuk mengumpulkan fakta dari sumber primer.

2. **Strukturkan Outline Terlebih Dahulu** sebelum menulis isi:
   - Tampilkan outline lengkap dan tunggu konfirmasi (kecuali user minta langsung dieksekusi tanpa jeda).

3. **Format Dokumen Standar Internasional (IMRaD / APA 7th)**:
   ```
   📄 [JUDUL DALAM HURUF KAPITAL]
   Penulis: [Nama] | Tanggal: [YYYY-MM-DD]
   ─────────────────────────────────────
   
   ABSTRAK (150-250 kata)
   [Ringkasan singkat: latar, metode, temuan utama, implikasi]
   
   Kata Kunci: [keyword1], [keyword2], [keyword3]
   
   1. PENDAHULUAN
      1.1 Latar Belakang
      1.2 Rumusan Masalah
      1.3 Tujuan
   
   2. TINJAUAN PUSTAKA / LANDASAN TEORI
   
   3. METODOLOGI / PENDEKATAN ANALISIS
   
   4. TEMUAN & PEMBAHASAN
      4.1 [Sub-topik 1]
      4.2 [Sub-topik 2]
      [Sertakan tabel data / bagan perbandingan jika relevan]
   
   5. KESIMPULAN & REKOMENDASI
   
   DAFTAR PUSTAKA (Format APA 7th)
   [Penulis, A. B. (Tahun). Judul karya. Penerbit. https://doi.org/xxxxx]
   ```

4. **Tabel Perbandingan & Executive Summary**:
   - Untuk laporan panjang (>1.500 kata), selalu sertakan Executive Summary 1 halaman di awal (Gaya GPT Researcher).
   - Sertakan tabel perbandingan, grafik tekstual, atau bullet evidence jika data kuantitatif tersedia.

---

## 3. STANDAR B — Laporan Formal Nasional Indonesia

### Format Baku (Kemendikbudristek / BRIN / Skripsi / Makalah):
```
📄 JUDUL LAPORAN
Institusi / Unit Kerja | Tanggal
─────────────────────────────────────

BAB I PENDAHULUAN
  1.1 Latar Belakang
  1.2 Rumusan Masalah
  1.3 Tujuan Penulisan
  1.4 Manfaat Penulisan

BAB II TINJAUAN PUSTAKA

BAB III METODOLOGI
  3.1 Pendekatan
  3.2 Teknik Pengumpulan Data
  3.3 Teknik Analisis Data

BAB IV PEMBAHASAN DAN ANALISIS HASIL
  4.1 [Sub-Bab Temuan 1]
  4.2 [Sub-Bab Temuan 2]

BAB V PENUTUP
  5.1 Kesimpulan
  5.2 Saran

DAFTAR PUSTAKA (Alfabetis, format Chicago/MIPA)
```

### Ketentuan Teknis:
- **Font**: Times New Roman 12pt (untuk dokumen cetak) atau Inter/Arial 11pt (digital)
- **Spasi**: 1,5 spasi
- **Margin**: 4 cm (kiri), 4 cm (atas), 3 cm (kanan), 3 cm (bawah) — standar jilid S1/S2
- **Penomoran halaman**: Angka romawi kecil (i, ii, iii) untuk halaman awal; angka Arab (1, 2, 3) mulai BAB I
- Setiap sub-bab diakhiri dengan paragraf transisi pengantar ke sub-bab berikutnya

---

## 4. STANDAR C — Artikel Opini (Gaya Kompas / Tempo / Project Syndicate)

### Filosofi:
Artikel opini bukan rangkuman netral. Ia harus punya:
- **Stance yang tegas** (tidak plinplan, tidak "di satu sisi... di sisi lain...")
- **Suara yang khas** dan berkarakter
- **Argumen yang menyerang akar masalah**, bukan permukaan fenomena

### Struktur Wajib Artikel Opini (700-1.000 kata):
```
[JUDUL PROVOKATIF — tajam, bukan clickbait]
[SUBJUDUL opsional — maksimal 1 kalimat konteks]

── Paragraf 1: HOOK (1-2 kalimat)
   Fenomena aktual / paradoks / fakta mengejutkan / kutipan bertenaga.
   Tujuan: Pembaca TIDAK BOLEH berhenti membaca setelah kalimat pertama.

── Paragraf 2: TESIS
   Nyatakan posisi/pendapat utama secara eksplisit dan berani.
   Contoh: "Saya berpendapat bahwa... karena..."

── Paragraf 3-5: BADAN ARGUMEN (2-3 poin utama)
   Setiap poin: [Klaim] → [Bukti/Data/Analogi] → [Implikasi]
   Gunakan analogi yang segar dan tidak klise.

── Paragraf 6: STEELMANNING (Menjawab Keberatan Lawan)
   Akui argumen paling kuat dari sisi berlawanan, lalu patahkan secara elegan.
   "Memang benar bahwa... Namun hal ini justru memperkuat tesis bahwa..."

── Paragraf 7: PENUTUP / PUNCHLINE
   Kalimat pamungkas yang memantik renungan, bukan sekadar kesimpulan.
   Idealnya: kembali ke hook pembuka dengan twist yang tak terduga.
```

### Larangan Keras dalam Artikel Opini:
- ❌ Jangan buka dengan "Pada era globalisasi saat ini..."
- ❌ Jangan gunakan klise: "pro dan kontra", "bak pisau bermata dua", "tidak terlepas dari"
- ❌ Jangan akhiri dengan "Semoga bermanfaat bagi kita semua"
- ✅ Gunakan kalimat aktif, diksi presisi, dan ritme yang mengalir

---

## 5. OUTPUT FORMAT

### Untuk Semua Tipe Dokumen:
- Tulis dalam **Markdown** terlebih dahulu agar dapat disimpan langsung sebagai `.md`
- Jika user meminta format Word (`.docx`), gunakan `run_code` untuk generate dengan `python-docx`
- Jika panjang dokumen >2.000 kata, tawarkan opsi untuk menyimpan ke workspace

### Template Generate Word (.docx) dengan python-docx:
```python
from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH

doc = Document()

# Set margins (4-4-3-3 standard Indonesia)
section = doc.sections[0]
section.left_margin = Cm(4)
section.top_margin = Cm(4)
section.right_margin = Cm(3)
section.bottom_margin = Cm(3)

# Title
title = doc.add_heading(level=0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run("JUDUL LAPORAN")
run.bold = True
run.font.size = Pt(14)
run.font.name = "Times New Roman"

# Add content paragraphs with 1.5 line spacing
# ... (agent fills in actual content here)

doc.save("/app/workspace/laporan.docx")
```

---

## 6. SELF-CHECK SEBELUM OUTPUT
Sebelum menyerahkan dokumen kepada user, lakukan pemeriksaan:
- [ ] Apakah ada tesis/argumen utama yang jelas?
- [ ] Apakah struktur bab/bagian sudah konsisten?
- [ ] Apakah tidak ada kalimat bertele-tele atau repetitif?
- [ ] Apakah sitasi/referensi ada jika diperlukan?
- [ ] Apakah tone sudah sesuai permintaan (formal / semi-formal / opini)?
- [ ] Apakah dokumen siap disimpan ke workspace jika panjang >1.000 kata?
