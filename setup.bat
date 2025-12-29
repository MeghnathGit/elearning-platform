@echo off
echo ============================================
echo    EduSphere Pro - Professional Setup
echo ============================================

echo 1. Creating project structure...
if not exist "static\css" mkdir static\css
if not exist "static\js" mkdir static\js
if not exist "static\images" mkdir static\images
if not exist "templates" mkdir templates
if not exist "instance" mkdir instance

echo 2. Installing dependencies...
pip install Flask Werkzeug >nul 2>&1
if errorlevel 1 (
    echo Failed to install dependencies
    echo Please run: pip install Flask Werkzeug
    pause
    exit /b 1
)

echo 3. Setting up database...
python -c "
import sqlite3
from werkzeug.security import generate_password_hash

conn = sqlite3.connect('elearning.db')
c = conn.cursor()

# Create tables
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        is_admin BOOLEAN DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        category TEXT,
        instructor_id INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
''')

c.execute('''
    CREATE TABLE IF NOT EXISTS enrollments (
        user_id INTEGER,
        course_id INTEGER,
        enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        progress INTEGER DEFAULT 0,
        PRIMARY KEY (user_id, course_id)
    )
''')

# Create admin
hashed_pw = generate_password_hash('admin123')
c.execute('''
    INSERT OR IGNORE INTO users (username, email, password, is_admin)
    VALUES ('admin', 'admin@edusphere.com', ?, 1)
''', (hashed_pw,))

# Sample courses
courses = [
    ('Python Programming', 'Master Python from basics to advanced', 'Programming', 1),
    ('Web Development', 'Build modern web applications', 'Web Development', 1),
    ('Data Science', 'Data analysis and visualization', 'Data Science', 1),
    ('Machine Learning', 'AI and ML fundamentals', 'Artificial Intelligence', 1),
    ('Cloud Computing', 'AWS, Azure, and Google Cloud', 'Cloud', 1),
    ('Cybersecurity', 'Security fundamentals and best practices', 'Security', 1)
]

for course in courses:
    c.execute('''
        INSERT OR IGNORE INTO courses (title, description, category, instructor_id)
        VALUES (?, ?, ?, ?)
    ''', course)

conn.commit()
conn.close()
print('Database setup complete!')
"

echo 4. Creating requirements.txt...
echo Flask==2.3.3 > requirements.txt
echo Werkzeug==2.3.7 >> requirements.txt

echo.
echo ============================================
echo    SETUP COMPLETE!
echo ============================================
echo.
echo To run the application:
echo 1. Open Command Prompt in this folder
echo 2. Run: python app.py
echo 3. Open browser: http://localhost:5000
echo.
echo Admin credentials: admin / admin123
echo.
pause