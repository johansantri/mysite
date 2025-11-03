# MYSITE

JakIja adalah Learning Management System (LMS) berbasis Python/Django yang dirancang untuk mendukung multiple‑vendor. Dengan JakIja, penyedia kursus dapat membuat, mengelola, dan menjual kursus online secara mandiri — cocok untuk institusi pendidikan, perusahaan, dan tim pelatihan.

## Ringkasan
- Repo asli: https://github.com/johansantri/mysite  
- Tujuan: platform pembelajaran online untuk tim/organisasi yang mudah dan ringan

## Fitur utama
- Manajemen pengguna (superuser, keuangan, kurasi, partner, instructor, learner, subscription, dsb)  
- Modul kursus, kurasi, keuangan, langganan, sertifikat  
- Mini social media mirip X, blog, LTI consumer  
- Metode kursus: gratis, bayar di depan, bayar ujian, bayar sertifikat, langganan

## Fitur tambahan
- Mendukung pembayaran dengan Tripay
- Mendukung Microcredential kursus atau kursus profesional sertifikat

## Persyaratan
- Python 3.8+ (disarankan)  
- Django 5.1

## Instalasi singkat (Linux)
1. git clone https://github.com/johansantri/mysite.git  
2. cd mysite  
3. python3 -m venv .venv  
4. source .venv/bin/activate  
5. python3 -m pip install -r requirements.txt  
6. python manage.py makemigrations  
7. python manage.py migrate  
8. python manage.py createsuperuser  
9. python manage.py runserver

## Demo / Video
<!-- iframe mungkin tidak dirender di GitHub, gunakan fallback thumbnail -->
<iframe width="560" height="315" src="https://www.youtube.com/embed/UXxBFmejhe8?si=vph4S-PCTeebwYpz" title="MYSITE demo" frameborder="0" allowfullscreen></iframe>

Fallback:  
[![MYSITE demo](https://img.youtube.com/vi/UXxBFmejhe8/maxresdefault.jpg)](https://www.youtube.com/watch?v=UXxBFmejhe8)

## Catatan migrasi
Jika ada migrasi lama bermasalah, cadangkan lalu hapus file migrasi non‑esensial sebelum menjalankan `makemigrations`.

## Lisensi
Proyek ini dilisensikan di bawah MIT License — lihat file `LICENSE` untuk teks lengkap.

## Kontribusi
Pull request dipersilakan. Sertakan deskripsi perubahan dan tes bila perlu. Pertimbangkan menambahkan `CONTRIBUTING.md` dan `CODE_OF_CONDUCT.md`.

## Atribusi (wajib ditampilkan pada footer halaman resmi)
Pembuat / Creator: Johan Santri

## Kontak
Repository: https://github.com/johansantri/mysite

## Contoh akses dasar
- Superuser: admin@admin.com | admin  
- Partner: partner@partner.com | partner  
- Instructor: instructor@instructor.com | instructor  
- Learner: learn@learn.com | learn  
- Subscription: sub@sub.com | sub  
- Curation: curation@curation.com | curation  
- Finances: fin@fin.com | fin