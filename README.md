// ...existing code...
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
// ...existing code...
// ...existing code...
MIT License

Copyright (c) 2025 Johan Santri

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
// ...existing code...
// ...existing code...
{% load static %}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{% block title %}MYSITE{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/main.css' %}">
  {% block head %}{% endblock %}
</head>
<body>
  <header>
    {% block header %}
    <!-- navbar / header -->
    {% endblock %}
  </header>

  <main>
    {% block content %}{% endblock %}
  </main>

  <footer style="padding:16px;text-align:center;border-top:1px solid #eee;margin-top:32px;">
    <div>
      © {% now "Y" %} MYSITE — Pembuat / Creator: <a href="https://github.com/johansantri" target="_blank" rel="noopener noreferrer">Johan Santri</a>
    </div>
  </footer>

  <script src="{% static 'js/main.js' %}"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
// ...existing code...