# 🍱 Canteen Express - Backend Setup Guide

Welcome sa **Canteen Express** project! 🎉

Sundin ang step-by-step guide na ito para ma-setup at mapatakbo nang maayos ang **Django backend** sa inyong local machine.

---

## 📋 Prerequisites

Bago magsimula, siguraduhing naka-install ang mga sumusunod sa iyong computer:

- **Python 3.10+**  
  - Recommended: **Python 3.12**
- **Git**
- **VS Code** or any code editor

---

# 🚀 Quick Start

## 1. Clone the Repository & Navigate to Backend

Buksan ang **Terminal / PowerShell** at i-run:

```bash
git clone https://github.com/CanteenExp/Canteen-Express.git
cd "CANTEEN EXPRESS/backend"
```

> **Note:** Palitan ang `<REPOSITORY_URL_HERE>` ng actual GitHub repository URL.

---

## 2. Create and Activate Virtual Environment

### 🪟 Windows - PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate
```

### 🪟 Windows - Command Prompt (CMD)

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

### 🍎 Mac / 🐧 Linux

```bash
python3 -m venv venv
source venv/bin/activate
```

> ⚠️ **Important:** Siguraduhing may `(venv)` na nakikita sa unahan ng terminal bago magpatuloy.
>
> Example:
>
> ```text
> (venv) PS C:\...\CANTEEN EXPRESS\backend>
> ```

---

## 3. Install Dependencies

I-install ang lahat ng required packages gamit ang:

```bash
pip install -r requirements.txt
```

### Kung wala pang `requirements.txt`

I-install ang pangunahing dependencies:

```bash
pip install django python-dotenv psycopg2-binary
```

---

## 4. Setup Environment Variables

### Create `.env` File

Gumawa ng bagong file sa loob ng:

```text
backend/
```

Ilagay ito sa parehong folder kung nasaan ang `manage.py`.

Ang structure ay dapat ganito:

```text
backend/
├── manage.py
├── .env
├── requirements.txt
├── config/
├── accounts/
└── ...
```

> 🛑 **IMPORTANT:** Siguraduhing ang filename ay:
>
> ```text
> .env
> ```
>
> at **HINDI**:
>
> ```text
> .env.txt
> ```

### `.env` Contents

I-paste ang following environment variables sa `.env`:

```env
SECRET_KEY="django-insecure-your-secret-key-here"
DEBUG=True

# Neon Cloud Database Credentials
DB_NAME="neondb"
DB_USER="neondb_owner"
DB_PASSWORD="<HINGIIN_ANG_PASSWORD_SA_PROJECT_LEAD>"
DB_HOST="ep-shy-heart-ayghwl06-pooler.c-5.us-east-2.aws.neon.tech"
DB_PORT="5432"
```

### 🔐 Security Reminder

**Huwag i-commit o i-push ang `.env` file sa GitHub.**

Siguraduhing kasama ang `.env` sa `.gitignore`:

```gitignore
.env
```

> ⚠️ **Never share your actual database password or Django `SECRET_KEY` publicly.**

---

## 5. Run Database Migrations

Siguraduhing updated ang database tables:

```bash
python manage.py migrate
```

### Kapag may binago sa Models

Kung may binago o gumawa ng bagong model sa iyong branch, patakbuhin:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

## 6. Create Admin Account (Optional)

Kung kailangan mo ng access sa **Django Admin Dashboard**, gumawa ng superuser:

```bash
python manage.py createsuperuser
```

Sundin ang instructions sa terminal para gumawa ng:

- Username
- Email
- Password

Pagkatapos nito, maa-access ang Django Admin sa:

```text
http://127.0.0.1:8000/admin/
```

---

## 7. Run Development Server

Patakbuhin ang Django development server:

```bash
python manage.py runserver
```

Kapag successful, dapat may makita kang output na parang:

```text
Starting development server at http://127.0.0.1:8000/
```

Buksan sa browser:

```text
http://127.0.0.1:8000/
```

---

# 🔄 Daily Development Workflow

Every time na mag-start ka ng development:

### 1. Navigate to Backend

```bash
cd "CANTEEN EXPRESS/backend"
```

### 2. Activate Virtual Environment

**PowerShell:**

```powershell
.\venv\Scripts\Activate
```

### 3. Pull Latest Changes

```bash
git pull
```

### 4. Install New Dependencies (if needed)

```bash
pip install -r requirements.txt
```

### 5. Apply Database Migrations

```bash
python manage.py migrate
```

### 6. Start Django Server

```bash
python manage.py runserver
```

---

# 🛠️ Common Commands

| Command | Purpose |
|---|---|
| `python manage.py runserver` | Start development server |
| `python manage.py makemigrations` | Create migrations from model changes |
| `python manage.py migrate` | Apply migrations |
| `python manage.py createsuperuser` | Create admin account |
| `python manage.py shell` | Open Django shell |
| `pip install -r requirements.txt` | Install project dependencies |
| `pip freeze > requirements.txt` | Update requirements file |

---

# 📁 Backend Structure

A typical backend structure should look similar to:

```text
CANTEEN EXPRESS/
│
├── backend/
│   ├── manage.py
│   ├── .env
│   ├── requirements.txt
│   │
│   ├── config/
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── accounts/
│   ├── canteen_menu/
│   └── ...
│
├── frontend/
│   └── ...
│
└── README.md
```

---

# ⚠️ Troubleshooting

### `ModuleNotFoundError`

Make sure the virtual environment is activated:

```powershell
.\venv\Scripts\Activate
```

Then reinstall dependencies:

```bash
pip install -r requirements.txt
```

---

### `.env` Not Working

Check that:

1. The file is named exactly `.env`
2. It is inside the `backend/` folder
3. It is located beside `manage.py`
4. The environment variables are spelled correctly
5. The actual database password is correct

---

### Database Connection Error

Check your Neon database credentials:

```env
DB_NAME="neondb"
DB_USER="neondb_owner"
DB_PASSWORD="YOUR_PASSWORD"
DB_HOST="YOUR_HOST"
DB_PORT="5432"
```

If you don't have the database password, **ask the project lead** instead of committing or sharing credentials publicly.

---

# 👥 For Canteen Express Developers

Before pushing your changes:

```bash
git status
```

Review your changed files and make sure that sensitive files such as `.env` are **not included**.

Then:

```bash
git add .
git commit -m "Your commit message"
git push
```

> 💡 Follow the team's Git branching workflow before pushing changes to shared branches.

---

# 🎯 Ready to Develop!

Once the server is running successfully:

```text
http://127.0.0.1:8000/
```

You're ready to start working on **Canteen Express**! 🍱🚀

**Happy coding, team! 💻**