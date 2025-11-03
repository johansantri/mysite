# MYSITE

MYSITE adalah aplikasi LMS (Learning Management System) berbasis Python/Django yang dirancang khusus untuk kebutuhan multiple vendor.

## Ringkasan
- Repo asli: https://github.com/johansantri/mysite  
- Tujuan: platform pembelajaran online untuk tim/organisasi

## Fitur utama
- Manajemen pengguna (superuser, partner, instructor, learner, subscription, dsb)  
- Modul kursus, kurasi, keuangan, langganan, sertifikat  
- Mini sosial media mirip X  
- Blog  
- Belajar mandiri  
- Metode kursus: gratis, bayar di depan, bayar ujian, bayar sertifikat, dan langganan

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