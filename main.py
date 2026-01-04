from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-12345')

# Database setup
def get_db():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()
    
    # Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            is_admin BOOLEAN DEFAULT 0
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
            level TEXT DEFAULT 'Beginner'
        )
    ''')
    
    # Enrollments table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS enrollments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            course_id INTEGER,
            progress INTEGER DEFAULT 0
        )
    ''')
    
    # Add admin user
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
            ('admin', 'admin@cognilearn.com', generate_password_hash('admin123'), 1)
        )
    except:
        pass
    
    # Add sample courses
    courses = [
        ('Python Programming', 'Learn Python from scratch', 'Programming', 'John Doe', 40, 'Beginner'),
        ('Web Development', 'Build websites with Flask', 'Web Dev', 'Jane Smith', 60, 'Intermediate'),
        ('Data Science', 'Introduction to Data Analysis', 'Data', 'Mike Johnson', 80, 'Advanced')
    ]
    
    for course in courses:
        cursor.execute(
            "INSERT OR IGNORE INTO courses (title, description, category, instructor, duration, level) VALUES (?, ?, ?, ?, ?, ?)",
            course
        )
    
    conn.commit()
    conn.close()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM courses LIMIT 3')
    courses = cursor.fetchall()
    conn.close()
    return render_template('index.html', 
                         featured_courses=courses, 
                         user=session.get('user_id'))

@app.route('/about')
def about():
    return render_template('about.html', user=session.get('user_id'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['is_admin'] = user['is_admin']
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        hashed = generate_password_hash(password)
        
        conn = get_db()
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed)
            )
            conn.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except:
            flash('Username or email already exists', 'danger')
        finally:
            conn.close()
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user_id']
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.*, e.progress 
        FROM enrollments e 
        JOIN courses c ON e.course_id = c.id 
        WHERE e.user_id = ?
    ''', (user_id,))
    enrolled = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         enrolled_courses=enrolled,
                         username=session['username'])

@app.route('/courses')
def courses():
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM courses')
    courses_list = cursor.fetchall()
    
    conn.close()
    
    return render_template('courses.html', courses=courses_list)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    conn = get_db()
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
    
    conn.close()
    
    if not course:
        flash('Course not found', 'danger')
        return redirect(url_for('courses'))
    
    return render_template('course_detail.html',
                         course=course,
                         is_enrolled=is_enrolled)

@app.route('/enroll/<int:course_id>')
@login_required
def enroll(course_id):
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?',
        (user_id, course_id)
    )
    if cursor.fetchone():
        flash('Already enrolled', 'info')
    else:
        cursor.execute(
            'INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)',
            (user_id, course_id)
        )
        flash('Enrolled successfully!', 'success')
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/my-courses')
@login_required
def my_courses():
    user_id = session['user_id']
    
    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.*, e.progress 
        FROM enrollments e 
        JOIN courses c ON e.course_id = c.id 
        WHERE e.user_id = ?
    ''', (user_id,))
    courses_list = cursor.fetchall()
    
    conn.close()
    
    return render_template('my_courses.html', courses=courses_list)

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server starting on http://localhost:{port}")
    print("👤 Admin login: admin / admin123")
    app.run(host='0.0.0.0', port=port, debug=False)