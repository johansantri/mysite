
# MYSITE

MYSITE adalah aplikasi LMS (Learning Management System) berbasis Python/Django.

Ringkasan
- Repo asli: https://github.com/johansantri/mysite
- Tujuan: platform pembelajaran online untuk tim/organisasi

Fitur utama
- Manajemen pengguna (superuser, partner, instructor, learner, dsb)
- Modul kursus, kurasi, keuangan, langganan, sertifikat

Persyaratan
- Python 3.8+ (disarankan)
- Django 5.1

Instalasi singkat (Linux)
1. git clone https://github.com/johansantri/mysite.git  
2. cd mysite  
3. python3 -m venv .venv  
4. source .venv/bin/activate  
5. python3 -m pip install -r requirements.txt  
6. python manage.py makemigrations  
7. python manage.py migrate  
8. python manage.py createsuperuser  
9. python manage.py runserver

Catatan migrasi
- Jika ada migrasi lama bermasalah, cadangkan lalu hapus file migrasi non-esensial sebelum menjalankan makemigrations.

Lisensi
- Proyek ini dilisensikan di bawah MIT License. Lihat file LICENSE untuk detail.

Kontribusi
- Pull request dipersilakan. Sertakan deskripsi perubahan dan tes bila perlu.
- Pertimbangkan menambahkan CONTRIBUTING.md dan CODE_OF_CONDUCT.md.

Atribusi (wajib ditampilkan pada footer halaman resmi)
Pembuat / Creator: Johan Santri  
Halaman resmi aplikasi wajib menampilkan baris atribusi di footer aplikasi (contoh ada di templates/base.html).

Kontak
- Repository: https://github.com/johansantri/mysite


