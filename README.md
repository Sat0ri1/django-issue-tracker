# Django Issue Tracker

A simple issue tracker built with Django.

## 🚀 Quickstart

### 1. Clone the repository

```sh
git clone https://github.com/Sat0ri1/django-issue-tracker.git
cd django-issue-tracker
```

### 2. Create your `.env` file

Copy the example file and set your own secret key:

```sh
cp .env.example .env
```

Edit `.env` and set a secure value for `SECRET_KEY`:

```
SECRET_KEY=replace-this-with-your-own-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

You can generate a secret key in Python:

```python
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

### 3. Install dependencies

If you use [uv](https://github.com/astral-sh/uv) and have `uv.lock`:

```sh
uv sync
```

If you want to use `requirements.txt` (optional):

```sh
pip install -r requirements.txt
```

### 4. Apply migrations

```sh
python manage.py migrate
```

### 5. Create a superuser (for admin access)

```sh
python manage.py createsuperuser
```

### 6. Run the development server

```sh
python manage.py runserver
```

Visit [http://localhost:8000](http://localhost:8000) in your browser.

---

## 🎨 Frontend Setup (TailwindCSS & DaisyUI)

This project uses [TailwindCSS](https://tailwindcss.com/) and [DaisyUI](https://daisyui.com/) for styling.

### 1. Install Node.js dependencies

Make sure you have [Node.js](https://nodejs.org/) installed.

```sh
npm install
```

### 2. Build CSS

To build and watch CSS changes during development, run:

```sh
npm run build:css
```

This will compile `src/input.css` to `static/css/tailwind.css` using TailwindCSS.

### 3. Configuration files

- `tailwind.config.js` – TailwindCSS configuration
- `postcss.config.js` – PostCSS configuration
- `package.json` – npm scripts and dependencies

**Note:**  
You need to run the CSS build command for styles to appear correctly in the app.

---

## 🛠️ Notes

- The `.env` file is required for the project to start.  
- `.env.example` is provided as a template—**do not commit your real `.env**`!
- All dependencies are managed via `uv.lock` (or `requirements.txt` if you prefer).
- For production, set `DEBUG=False` and configure `ALLOWED_HOSTS` appropriately.

---

## 🧑‍💻 Useful commands

- Run tests:
  ```sh
  uv sync --dev
  pytest
  ```
- Access Django admin: [http://localhost:8000/admin](http://localhost:8000/admin)

---

## 💡 Troubleshooting

- If you see `ImproperlyConfigured: SECRET_KEY not found`, make sure your `.env` file exists and is filled out.
- If you use a different database, update your `.env` and `settings.py` accordingly.

---

**Enjoy building!**