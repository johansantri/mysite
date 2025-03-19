# What is MYSITE

MYSITE is a Python Django-based LMS (Learning Management System) application.

*******************
Release Information
*******************

This repository is designed for team collaboration in the development of the LMS.
For more details, visit the [repository page](https://github.com/johansantri/mysite).

**************************
Changes and Development of LMS Application
**************************

*******************
Requirements
*******************

- Django 5.1.

This application runs on Python 3 with the Django 5.1 framework.

************
Installation
************

Follow the instructions below to get started with the application.

***************
# Testing Website
Python project exploration using the Django framework.

## Role Access
- Superuser: admin@admin.com | admin
- Partner: partner@partner.com | partner
- Instructor: instructor@instructor.com | instructor
- Learner: learn@learn.com | learn
- And others

## Installation

Make sure you have **Python** and **pip** installed on your system before starting.

### 1. Clone this repository:
```shell
git clone https://github.com/johansantri/mysite.git
```
### 2. Navigate to the project directory:
```shell
cd mysite
```
### 3. Create a virtual environment:
Refer to this guide for setting up a virtual environment for your OS using linux: [Python Virtual Environment Installation Guide](https://packaging.python.org/en/latest/guides/installing-using-pip-and-virtual-environments/)
```shell
python3 -m venv .venv
```
### 4. Activate the virtual environment:
```shell
source .venv/bin/activate

```
### 5. Install requests package:
```shell
python3 -m pip install requests
```

### 6. Install dependencies from requirements.txt:
```shell
python3 -m pip install -r requirements.txt
```
### 7. Freeze requirements (to track package versions):
```shell
pip freeze > requirements.txt

```
### 8.Run makemigrations:
```shell
python manage.py makemigrations
```
****
Note: Make sure Python is installed before running this command, and that you have cleared the contents of the migrations folders (course, auth, authentication) in mysite\authentication\migrations. For example, remove all migration files like 001_ and any higher numbers.
****

### 9. Run database migrations:
```shell
python manage.py migrate
```
### 10. Run the server:
```shell
python manage.py runserver
```
### 11. To create a superuser:
```shell
python manage.py createsuperuser
```
****
Steps to create a superuser:

Enter your email, for example: admin@admin.com
Enter your username, for example: admin
Enter your password, for example: admin
Re-enter your password
Select "yes" to continue
****