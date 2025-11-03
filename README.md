# JakIja

JakIja is a Learning Management System (LMS) built with Python and Django, designed for multi‑vendor use. With JakIja, course providers can create, manage, and sell courses independently — suitable for educational institutions, companies, and training teams.

## Overview
- Original repo: https://github.com/johansantri/mysite  
- Goal: lightweight, team‑oriented online learning platform

## Key features
- User management (superuser, finance, curation, partner, instructor, learner, subscription, etc.)  
- Course, curation, finance, subscription, and certificate modules  
- Mini social feed (similar to X), blog, LTI consumer  
- Course delivery modes: free, upfront payment, exam payment, certificate payment, subscription

## Additional features
- Payment gateway support: Tripay  
- Micro‑credentials / professional certificate support

## Requirements
- Python 3.8+ (recommended)  
- Django 5.1

## Quick install (Linux)
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
 
[![MYSITE demo](https://img.youtube.com/vi/UXxBFmejhe8/maxresdefault.jpg)](https://www.youtube.com/watch?v=UXxBFmejhe8)

## Migration notes
If you encounter issues with old migrations, back up and remove non‑essential migration files for the affected apps before running `makemigrations`.

## License
This project is licensed under the MIT License — see `LICENSE` for details.

## Contributing
Pull requests are welcome. Please include a description of changes and tests when applicable. Consider adding `CONTRIBUTING.md` and `CODE_OF_CONDUCT.md`.

## Attribution (must appear on the official site footer)
Creator: Johan Santri  
The official site must display this attribution in the footer (example: `templates/base.html`).

## Contact
Repository: https://github.com/johansantri/mysite

## Demo accounts
- Superuser: admin@admin.com | admin  
- Partner: partner@partner.com | partner  
- Instructor: instructor@instructor.com | instructor  
- Learner: learn@learn.com | learn  
- Subscription: sub@sub.com | sub  
- Curation: curation@curation.com | curation  
- Finances: fin@fin.com | fin