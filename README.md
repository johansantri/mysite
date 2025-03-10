####
What is MYSITE
####

MYSITE merupakan pengembangan aplikasi LMS berbasis Python Django.

*******************
Release Information
*******************

Repo ini dirancang untuk bekerja team dalam pembuatan LMS
<https://github.com/johansantri/mysite>`_ page.

**************************
Perubahan dan Pengembangan Aplikasi LMS
**************************

*******************
Kebutuhan Requirements
*******************

Django 5.1.

Aplikasi ini berjalan di Python 3 dengan framework Django 5.1.

************
Installasi
************

Perhatikan Panduan dibawah ini untuk memulai aplikasi

***************
# Testing Website
Proyek eksplorasi Python menggunakan framework Django.

## Akses Role
- Superuser admin@admin.com | admin
- Staf
- Partner staf@staf.com | staf
- Instructor instructor@instructor.com | instructor
- Learner learn@learn.com | learn
- Dan lainnya

## Instalasi

Pastikan Anda telah menginstal **Python** dan **pip** di sistem Anda sebelum memulai.

### 1. Clone repositori ini:
```shell
git clone https://github.com/johansantri/mysite.git
```
### 2. Pindah ke direktori proyek:
```shell
cd mysite
```
### 3. Buat virtual environment:
Anda bisa melihat referensi berikut <https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/> jenis OS dalam menggunakan virtual environment ini menggunakan Windows
```shell
py -m venv .venv
```
### 4. Aktifkan virtual environment:
```shell
.venv\Scripts\activate
```

### 5. Install requests:
```shell
py -m pip install requests
```
### 6. Install dependencies dari requirements.txt:
```shell
py -m pip install -r requirements.txt
```
### 7. Freeze requirements (untuk mencatat versi package):
```shell
py -m pip freeze
```
### 8.Jalankan server
``` shell
python manage.py runserver
```
jika mengalami kendala, coba ikuti langkah dibawah ini
### 9. Salin data dari models.py:

ulangi proses dari awal

*****
### 10. Jalankan makemigrations:
```shell
python manage.py makemigrations
```

Catatan:
Pastikan Anda sudah menginstal **Python** sebelum menjalankan perintah ini.
dan Anda sudah menghapus semua isi dari folder migrations [course, auth, authentication]
**mysite\authentication\migrations**
contoh 001_ sd angka terbesar

### 11. Jalankan migrasi database:
```shell
python manage.py migrate
```
### 12. Jalankan server:
```shell
python manage.py runserver
```
### 13. Untuk membuat superuser:
```shell
python manage.py createsuperuser
```
****
Langkah-langkah untuk membuat superuser:

Masukkan email Anda, contoh: admin@admin.com
Masukkan username Anda, contoh: admin
Masukkan password Anda, contoh: admin
Ulangi password Anda
Pilih yes untuk melanjutkan
****
### 14. Jalankan Server:
```shell
python manage.py runserver
```
Akses url **http://127.0.0.1:8000/**
