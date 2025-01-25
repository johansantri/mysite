###################
What is MYSITE
###################

MYSITE merupakan pengembangan aplikasi LMS berbasis  Python Django .

*******************
Release Information
*******************

Repo  ini dirancang untuk bekerja team dalam pembuatan LMS
<https://github.com/johansantri/mysite>`_ page.

**************************
Perubahan dan Pengembangan Aplikasi LMS
**************************


*******************
Kebutuhan Requirements
*******************

Django 5.1.

Aplikasi ini berjalan di python 3 dengan framework Django 5.1.

************
Installasi
************

Perhatikan Panduan dibawah ini untuk memulai aplikasi





***************
# Testing Website
Proyek eksplorasi Python menggunakan framework Django.

## Akses Role
- Superuser
- Staf
- Partner
- Instructor
- Learner
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
anda bisa melihat refrensi berikut <https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/> jenis OS
```shell
py -m venv .venv
```
### 4. Aktifkan virtual environment:
```shell
.venv\Scripts\activate
```
### 5. Upgrade pip:
```shell
py -m pip install --upgrade pip
```
### 6. Install requests:
```shell
py -m pip install requests
```
### 7. Install dependencies dari requirements.txt:
```shell
py -m pip install -r requirements.txt
```
### 8. Freeze requirements (untuk mencatat versi package):
```shell
py -m pip freeze
```
### 9. Salin data dari models.py:

*****
Sebelum menjalankan aplikasi, salin data dari models.py ke direktori Anda, misalnya ke path **mysite\.venv\lib\site-packages\django\contrib\auth.**
Pastikan untuk menyalin seluruh isi **models.py.**
*****
### 10. Jalankan makemigrations:
```shell
python manage.py makemigrations
```

Catatan:
Pastikan Anda sudah menginstal **Python** sebelum menjalankan perintah ini.

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