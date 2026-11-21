# NumPy Flask Online Exam

## Setup (Windows CMD)
```cmd
python -m venv venv
venv\\Scripts\\activate
pip install -r requirements.txt
copy .env.example .env
```
Edit `.env` and set your own `SECRET_KEY`, `EXAM_VERIFICATION_CODE`, `ADMIN_USERNAME`, and `ADMIN_PASSWORD`.

## Run
```cmd
python app.py
```
Open http://127.0.0.1:5000

## Student flow
Register -> login -> enter instructor's shared exam verification code -> answer 100 MCQs -> submit -> automatic score.

## Admin flow
Open http://127.0.0.1:5000/admin/login. Use credentials from `.env`. Download separate Excel files for registered students and exam results.

## Storage and behavior
- SQLite: `instance/exam.db`
- Questions and answer key: `data/questions.json` (answer key stays server-side; browser receives questions/options only)
- One submitted attempt per student account.
- Supports multiple students at once through individual Flask sessions and database records.
- Excel workbooks are generated on demand from SQLite.

## Important
Change all default secrets before use. Keep `.env` private and do not commit it. Use HTTPS and a production WSGI server for public hosting. SQLite is suitable for small/moderate classes; use PostgreSQL for larger deployments. This starter does not include a timer, question shuffling, or webcam monitoring.
