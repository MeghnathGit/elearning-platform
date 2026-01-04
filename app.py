from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import sys
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Import database based on environment
try:
    import psycopg2
    import psycopg2.extras
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    import sqlite3

app = Flask(__name__)

# Configuration
app.secret_key = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=7)

# Secure cookies only in production
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('FLASK_ENV') == 'production'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

def get_db_connection():
    """Get database connection (PostgreSQL on Railway, SQLite locally)"""
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and POSTGRES_AVAILABLE:
        # PostgreSQL on Railway
        if database_url.startswith('postgres://'):
            database_url = database_url.replace('postgres://', 'postgresql://', 1)
        
        conn = psycopg2.connect(database_url, sslmode='require')
        conn.autocommit = False
        return conn
    else:
        # SQLite for local development
        conn = sqlite3.connect('elearning.db')
        conn.row_factory = sqlite3.Row
        return conn

def init_db():
    """Initialize database with tables"""
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            # SQLite schema
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Courses table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS courses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    description TEXT,
                    category TEXT,
                    instructor TEXT DEFAULT 'Admin',
                    duration INTEGER DEFAULT 40,
                    level TEXT DEFAULT 'Beginner',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Enrollments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enrollments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    course_id INTEGER,
                    progress INTEGER DEFAULT 0,
                    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    UNIQUE(user_id, course_id)
                )
            ''')
            
            conn.commit()
            
        else:
            # PostgreSQL schema
            cursor = conn.cursor()
            
            # Users table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    is_admin BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Courses table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS courses (
                    id SERIAL PRIMARY KEY,
                    title VARCHAR(200) NOT NULL,
                    description TEXT,
                    category VARCHAR(50),
                    instructor VARCHAR(100) DEFAULT 'Admin',
                    duration INTEGER DEFAULT 40,
                    level VARCHAR(20) DEFAULT 'Beginner',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Enrollments table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS enrollments (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER,
                    course_id INTEGER,
                    progress INTEGER DEFAULT 0,
                    enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    UNIQUE(user_id, course_id)
                )
            ''')
            
            conn.commit()
        
        # Add default admin
        try:
            if isinstance(conn, sqlite3.Connection):
                cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                if cursor.fetchone() is None:
                    hashed_pw = generate_password_hash('admin123')
                    cursor.execute(
                        "INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
                        ('admin', 'admin@cognilearn.com', hashed_pw, 1)
                    )
            else:
                cursor.execute("SELECT id FROM users WHERE username = 'admin'")
                if cursor.fetchone() is None:
                    hashed_pw = generate_password_hash('admin123')
                    cursor.execute(
                        "INSERT INTO users (username, email, password, is_admin) VALUES (%s, %s, %s, %s)",
                        ('admin', 'admin@cognilearn.com', hashed_pw, True)
                    )
            
            conn.commit()
            
            # Add sample courses if empty
            cursor.execute("SELECT COUNT(*) FROM courses")
            count = cursor.fetchone()[0]
            
            if count == 0:
                sample_courses = [
                    ('Python Programming Masterclass', 'Master Python from basics to advanced', 'Programming', 'Dr. Alex Johnson', 60, 'Intermediate'),
                    ('Web Development Bootcamp', 'Build modern websites', 'Web Development', 'Sarah Williams', 80, 'Beginner'),
                    ('Data Science Fundamentals', 'Learn data analysis and ML', 'Data Science', 'Dr. Michael Chen', 100, 'Advanced')
                ]
                
                if isinstance(conn, sqlite3.Connection):
                    for course in sample_courses:
                        cursor.execute(
                            "INSERT INTO courses (title, description, category, instructor, duration, level) VALUES (?, ?, ?, ?, ?, ?)",
                            course
                        )
                else:
                    for course in sample_courses:
                        cursor.execute(
                            "INSERT INTO courses (title, description, category, instructor, duration, level) VALUES (%s, %s, %s, %s, %s, %s)",
                            course
                        )
                
                conn.commit()
                
            print("✅ Database initialized successfully!")
            
        except Exception as e:
            print(f"⚠️ Could not add default data: {e}")
            conn.rollback()
            
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        if conn:
            conn.rollback()
        raise e
    finally:
        if conn:
            conn.close()

# Decorators
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            flash('Admin access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# =============== ROUTES ===============

@app.route('/')
def index():
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM courses LIMIT 3')
            featured = cursor.fetchall()
            
            cursor.execute('SELECT COUNT(*) FROM courses')
            total_courses = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM users')
            total_students = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM enrollments')
            total_enrollments = cursor.fetchone()[0]
        else:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM courses LIMIT 3')
            featured = cursor.fetchall()
            
            cursor.execute('SELECT COUNT(*) FROM courses')
            total_courses = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM users')
            total_students = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM enrollments')
            total_enrollments = cursor.fetchone()[0]
            
    except Exception as e:
        print(f"❌ Database error: {e}")
        featured = []
        total_courses = total_students = total_enrollments = 0
    finally:
        conn.close()
    
    stats = {
        'total_courses': total_courses,
        'total_students': total_students,
        'total_enrollments': total_enrollments
    }
    
    return render_template('index.html', 
                         featured_courses=featured, 
                         stats=stats,
                         user=session.get('user'))

@app.route('/about')
def about():
    return render_template('about.html', user=session.get('user'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        
        try:
            if isinstance(conn, sqlite3.Connection):
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
                user = cursor.fetchone()
            else:
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cursor.fetchone()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = user['is_admin']
                session['user'] = {
                    'id': user['id'],
                    'username': user['username'],
                    'email': user['email'],
                    'is_admin': user['is_admin']
                }
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid credentials', 'danger')
                
        except Exception as e:
            print(f"❌ Login error: {e}")
            flash('Database error occurred', 'danger')
        finally:
            conn.close()
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        hashed_password = generate_password_hash(password)
        
        conn = get_db_connection()
        
        try:
            if isinstance(conn, sqlite3.Connection):
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                    (username, email, hashed_password)
                )
            else:
                cursor = conn.cursor()
                cursor.execute(
                    'INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                    (username, email, hashed_password)
                )
            
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            print(f"❌ Registration error: {e}")
            flash('Username or email already exists', 'danger')
            conn.rollback()
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.*, e.progress, e.id as enrollment_id 
                FROM enrollments e 
                JOIN courses c ON e.course_id = c.id 
                WHERE e.user_id = ?
            ''', (user_id,))
            enrolled = cursor.fetchall()
            
            cursor.execute('SELECT * FROM courses ORDER BY RANDOM() LIMIT 3')
            featured = cursor.fetchall()
        else:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute('''
                SELECT c.*, e.progress, e.id as enrollment_id 
                FROM enrollments e 
                JOIN courses c ON e.course_id = c.id 
                WHERE e.user_id = %s
            ''', (user_id,))
            enrolled = cursor.fetchall()
            
            cursor.execute('SELECT * FROM courses ORDER BY RANDOM() LIMIT 3')
            featured = cursor.fetchall()
            
    except Exception as e:
        print(f"❌ Dashboard error: {e}")
        enrolled = []
        featured = []
    finally:
        conn.close()
    
    return render_template('dashboard.html', 
                         enrolled_courses=enrolled,
                         featured_courses=featured,
                         user=session.get('user'))

@app.route('/courses')
def courses():
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM courses ORDER BY title')
            courses_list = cursor.fetchall()
            
            cursor.execute('SELECT DISTINCT category FROM courses ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            
            cursor.execute('SELECT DISTINCT level FROM courses ORDER BY level')
            levels = [row[0] for row in cursor.fetchall()]
        else:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute('SELECT * FROM courses ORDER BY title')
            courses_list = cursor.fetchall()
            
            cursor.execute('SELECT DISTINCT category FROM courses ORDER BY category')
            categories = [row[0] for row in cursor.fetchall()]
            
            cursor.execute('SELECT DISTINCT level FROM courses ORDER BY level')
            levels = [row[0] for row in cursor.fetchall()]
            
    except Exception as e:
        print(f"❌ Courses error: {e}")
        courses_list = []
        categories = []
        levels = []
    finally:
        conn.close()
    
    return render_template('courses.html', 
                         courses=courses_list,
                         categories=categories,
                         levels=levels,
                         user=session.get('user'))

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM courses WHERE id = ?', (course_id,))
            course = cursor.fetchone()
            
            is_enrolled = False
            if 'user_id' in session:
                cursor.execute(
                    'SELECT * FROM enrollments WHERE user_id = ? AND course_id = ?',
                    (session['user_id'], course_id)
                )
                is_enrolled = cursor.fetchone() is not None
        else:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute('SELECT * FROM courses WHERE id = %s', (course_id,))
            course = cursor.fetchone()
            
            is_enrolled = False
            if 'user_id' in session:
                cursor.execute(
                    'SELECT * FROM enrollments WHERE user_id = %s AND course_id = %s',
                    (session['user_id'], course_id)
                )
                is_enrolled = cursor.fetchone() is not None
                
    except Exception as e:
        print(f"❌ Course detail error: {e}")
        course = None
        is_enrolled = False
    finally:
        conn.close()
    
    if not course:
        flash('Course not found', 'danger')
        return redirect(url_for('courses'))
    
    return render_template('course_detail.html',
                         course=course,
                         is_enrolled=is_enrolled,
                         user=session.get('user'))

@app.route('/enroll/<int:course_id>')
@login_required
def enroll(course_id):
    user_id = session['user_id']
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?',
                (user_id, course_id)
            )
            if cursor.fetchone():
                flash('You are already enrolled in this course', 'info')
            else:
                cursor.execute(
                    'INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)',
                    (user_id, course_id)
                )
                flash('Successfully enrolled in the course!', 'success')
        else:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT id FROM enrollments WHERE user_id = %s AND course_id = %s',
                (user_id, course_id)
            )
            if cursor.fetchone():
                flash('You are already enrolled in this course', 'info')
            else:
                cursor.execute(
                    'INSERT INTO enrollments (user_id, course_id) VALUES (%s, %s)',
                    (user_id, course_id)
                )
                flash('Successfully enrolled in the course!', 'success')
        
        conn.commit()
        
    except Exception as e:
        print(f"❌ Enrollment error: {e}")
        flash('Error enrolling in course', 'danger')
        conn.rollback()
    finally:
        conn.close()
    
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/my-courses')
@login_required
def my_courses():
    user_id = session['user_id']
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute('''
                SELECT c.*, e.progress 
                FROM enrollments e 
                JOIN courses c ON e.course_id = c.id 
                WHERE e.user_id = ?
            ''', (user_id,))
            courses_list = cursor.fetchall()
        else:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute('''
                SELECT c.*, e.progress 
                FROM enrollments e 
                JOIN courses c ON e.course_id = c.id 
                WHERE e.user_id = %s
            ''', (user_id,))
            courses_list = cursor.fetchall()
            
    except Exception as e:
        print(f"❌ My courses error: {e}")
        courses_list = []
    finally:
        conn.close()
    
    return render_template('my_courses.html',
                         courses=courses_list,
                         user=session.get('user'))

@app.route('/profile')
@login_required
def profile():
    user_id = session['user_id']
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            user = cursor.fetchone()
            
            cursor.execute('SELECT COUNT(*) FROM enrollments WHERE user_id = ?', (user_id,))
            enrolled_count = cursor.fetchone()[0]
        else:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
            user = cursor.fetchone()
            
            cursor.execute('SELECT COUNT(*) FROM enrollments WHERE user_id = %s', (user_id,))
            enrolled_count = cursor.fetchone()[0]
            
    except Exception as e:
        print(f"❌ Profile error: {e}")
        user = None
        enrolled_count = 0
    finally:
        conn.close()
    
    if not user:
        flash('User not found', 'danger')
        return redirect(url_for('index'))
    
    return render_template('profile.html',
                         user=user,
                         enrolled_count=enrolled_count)

@app.route('/admin')
@admin_required
def admin():
    conn = get_db_connection()
    
    try:
        if isinstance(conn, sqlite3.Connection):
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM users')
            users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM courses')
            courses = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM enrollments')
            enrollments = cursor.fetchone()[0]
            
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT 10')
            recent_users = cursor.fetchall()
        else:
            cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute('SELECT COUNT(*) FROM users')
            users = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM courses')
            courses = cursor.fetchone()[0]
            
            cursor.execute('SELECT COUNT(*) FROM enrollments')
            enrollments = cursor.fetchone()[0]
            
            cursor.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT 10')
            recent_users = cursor.fetchall()
            
    except Exception as e:
        print(f"❌ Admin error: {e}")
        users = courses = enrollments = 0
        recent_users = []
    finally:
        conn.close()
    
    stats = {
        'users': users,
        'courses': courses,
        'enrollments': enrollments
    }
    
    return render_template('admin.html',
                         stats=stats,
                         recent_users=recent_users,
                         user=session.get('user'))

@app.route('/admin/add_course', methods=['GET', 'POST'])
@admin_required
def add_course():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        instructor = request.form.get('instructor', 'Admin')
        duration = request.form.get('duration', 40)
        level = request.form.get('level', 'Beginner')
        
        conn = get_db_connection()
        
        try:
            if isinstance(conn, sqlite3.Connection):
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO courses (title, description, category, instructor, duration, level)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (title, description, category, instructor, duration, level))
            else:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT INTO courses (title, description, category, instructor, duration, level)
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (title, description, category, instructor, duration, level))
            
            conn.commit()
            flash('Course added successfully!', 'success')
            return redirect(url_for('admin'))
            
        except Exception as e:
            print(f"❌ Add course error: {e}")
            flash('Error adding course', 'danger')
            conn.rollback()
        finally:
            conn.close()
    
    return render_template('add_course.html', user=session.get('user'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.datetime.now().isoformat()})

if __name__ == '__main__':
    print("🚀 Starting eLearning Platform...")
    print(f"📦 Environment: {os.environ.get('FLASK_ENV', 'development')}")
    print(f"🔧 Debug mode: {os.environ.get('FLASK_DEBUG', 'True')}")
    
    # Initialize database
    try:
        init_db()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"⚠️ Database initialization warning: {e}")
    
    # Get port from environment (Railway provides this)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    print(f"🌐 Server running on http://0.0.0.0:{port}")
    print("👤 Admin login: admin / admin123")
    
    app.run(host='0.0.0.0', port=port, debug=False)