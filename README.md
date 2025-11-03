# MYSITE

JakIja adalah aplikasi Learning Management System (LMS) berbasis Python/Django yang dirancang untuk mendukung multiple vendor.
Dengan JakIja, setiap penyedia kursus dapat membuat, mengelola, dan menjual kursus online secara mandiri, mirip platform e-learning besar seperti Coursera, Udemy, dan edX.
Aplikasi ini cocok untuk organisasi, institusi pendidikan, atau perusahaan yang ingin membangun ekosistem pembelajaran online multi-penyedia .

## Ringkasan
- Repo asli: https://github.com/johansantri/mysite  
- Tujuan: platform pembelajaran online untuk tim/organisasi

## Fitur utama
- Manajemen pengguna (superuser, keuangan, kurasi, partner, instructor, learner, subscription, dsb)  
- Modul kursus, kurasi, keuangan, langganan, sertifikat  
- Mini sosial media mirip X  
- Blog  
- Belajar mandiri  
- Metode kursus: gratis, bayar di depan, bayar ujian, bayar sertifikat, dan langganan
- lti consumer

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

## Catatan migrasi
Jika ada migrasi lama bermasalah, cadangkan lalu hapus file migrasi non‑esensial sebelum menjalankan `makemigrations`.

## Demo / Video
<!-- Direct iframe (may not render on GitHub but works in many Markdown viewers / docs sites) -->
<iframe width="560" height="315" src="https://www.youtube.com/embed/UXxBFmejhe8?si=vph4S-PCTeebwYpz" title="YouTube video player" frameborder="0" allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe>

Fallback (recommended for GitHub): klik thumbnail di bawah untuk menonton di YouTube  
[![MYSITE demo](https://img.youtube.com/vi/UXxBFmejhe8/maxresdefault.jpg)](https://www.youtube.com/watch?v=UXxBFmejhe8)

> Catatan: GitHub strips iframes in README rendering for security. Gunakan thumbnail link di atas untuk memastikan pengunjung GitHub bisa melihat dan membuka video.

## Lisensi
Proyek ini dilisensikan di bawah MIT License — lihat file `LICENSE` untuk teks lengkap.

## Kontribusi
Pull request dipersilakan. Sertakan deskripsi perubahan dan tes bila perlu. Pertimbangkan menambahkan `CONTRIBUTING.md` dan `CODE_OF_CONDUCT.md`.

## Atribusi (wajib ditampilkan pada footer halaman resmi)
Pembuat / Creator: Johan Santri  
Halaman resmi aplikasi wajib menampilkan baris atribusi ini pada footer (contoh: `templates/base.html` atau `templates/home/base.html`).

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