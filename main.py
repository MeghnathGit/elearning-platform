from flask import Flask, render_template, request, redirect, url_for, flash, session
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import traceback

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-12345')

# Database setup - Use Railway's persistent storage if available
def get_db():
    # On Railway, use persistent database path
    if 'RAILWAY_VOLUME_MOUNT_PATH' in os.environ:
        db_path = os.path.join(os.environ['RAILWAY_VOLUME_MOUNT_PATH'], 'database.db')
    else:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    try:
        conn = get_db()
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
                user_id INTEGER NOT NULL,
                course_id INTEGER NOT NULL,
                progress INTEGER DEFAULT 0,
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE,
                UNIQUE(user_id, course_id)
            )
        ''')
        
        # Check if admin exists
        cursor.execute('SELECT id FROM users WHERE username = ?', ('admin',))
        admin_exists = cursor.fetchone()
        
        if not admin_exists:
            # Add admin user
            cursor.execute(
                "INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
                ('admin', 'admin@cognilearn.com', generate_password_hash('admin123'), 1)
            )
            
            # Add sample courses
            courses = [
                ('Python Programming', 'Learn Python from scratch', 'Programming', 'John Doe', 40, 'Beginner'),
                ('Web Development', 'Build websites with Flask', 'Web Dev', 'Jane Smith', 60, 'Intermediate'),
                ('Data Science', 'Introduction to Data Analysis', 'Data', 'Mike Johnson', 80, 'Advanced'),
                ('Machine Learning', 'AI and ML Fundamentals', 'AI', 'Dr. Alex Chen', 100, 'Advanced'),
                ('Mobile App Development', 'Build iOS & Android apps', 'Mobile', 'Sarah Wilson', 70, 'Intermediate')
            ]
            
            cursor.executemany(
                "INSERT INTO courses (title, description, category, instructor, duration, level) VALUES (?, ?, ?, ?, ?, ?)",
                courses
            )
        
        conn.commit()
        conn.close()
        print("✅ Database initialized successfully")
    except Exception as e:
        print(f"❌ Database initialization error: {e}")
        traceback.print_exc()

# Initialize database on startup
init_db()

# Login required decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Admin required decorator
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please login first', 'warning')
            return redirect(url_for('login'))
        if not session.get('is_admin'):
            flash('Admin access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def index():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses ORDER BY id DESC LIMIT 3')
        courses = cursor.fetchall()
        conn.close()
        
        return render_template('index.html', 
                             featured_courses=courses, 
                             user_id=session.get('user_id'),
                             username=session.get('username'),
                             is_admin=session.get('is_admin'))
    except Exception as e:
        print(f"Error in index route: {e}")
        return render_template('index.html', 
                             featured_courses=[], 
                             user_id=session.get('user_id'),
                             username=session.get('username'),
                             is_admin=session.get('is_admin'))

@app.route('/about')
def about():
    return render_template('about.html', 
                         user_id=session.get('user_id'),
                         username=session.get('username'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        
        if not username or not password:
            flash('Please fill all fields', 'danger')
            return render_template('login.html')
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE username = ? OR email = ?', 
                         (username, username))
            user = cursor.fetchone()
            conn.close()
            
            if user and check_password_hash(user['password'], password):
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['is_admin'] = bool(user['is_admin'])
                flash('Login successful!', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('Invalid username/email or password', 'danger')
        except Exception as e:
            print(f"Login error: {e}")
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        
        if not all([username, email, password]):
            flash('Please fill all fields', 'danger')
            return render_template('register.html')
        
        if len(password) < 6:
            flash('Password must be at least 6 characters', 'danger')
            return render_template('register.html')
        
        hashed = generate_password_hash(password)
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed)
            )
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username or email already exists', 'danger')
        except Exception as e:
            print(f"Registration error: {e}")
            flash('An error occurred. Please try again.', 'danger')
    
    return render_template('register.html')

@app.route('/dashboard')
@login_required
def dashboard():
    try:
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
        
        # Get recommended courses (not enrolled)
        cursor.execute('''
            SELECT * FROM courses 
            WHERE id NOT IN (
                SELECT course_id FROM enrollments WHERE user_id = ?
            )
            LIMIT 3
        ''', (user_id,))
        recommended = cursor.fetchall()
        
        conn.close()
        
        return render_template('dashboard.html', 
                             enrolled_courses=enrolled,
                             recommended_courses=recommended,
                             username=session['username'],
                             is_admin=session.get('is_admin'))
    except Exception as e:
        print(f"Dashboard error: {e}")
        flash('An error occurred loading your dashboard', 'danger')
        return redirect(url_for('index'))

@app.route('/courses')
def courses():
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        # Get search and filter parameters
        search = request.args.get('search', '')
        category = request.args.get('category', '')
        
        query = 'SELECT * FROM courses WHERE 1=1'
        params = []
        
        if search:
            query += ' AND (title LIKE ? OR description LIKE ? OR instructor LIKE ?)'
            search_term = f'%{search}%'
            params.extend([search_term, search_term, search_term])
        
        if category:
            query += ' AND category = ?'
            params.append(category)
        
        query += ' ORDER BY title'
        cursor.execute(query, params)
        courses_list = cursor.fetchall()
        
        # Get unique categories for filter
        cursor.execute('SELECT DISTINCT category FROM courses WHERE category IS NOT NULL ORDER BY category')
        categories = cursor.fetchall()
        
        conn.close()
        
        return render_template('courses.html', 
                             courses=courses_list,
                             categories=categories,
                             search=search,
                             selected_category=category,
                             user_id=session.get('user_id'),
                             username=session.get('username'))
    except Exception as e:
        print(f"Courses error: {e}")
        return render_template('courses.html', 
                             courses=[], 
                             categories=[],
                             user_id=session.get('user_id'))

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM courses WHERE id = ?', (course_id,))
        course = cursor.fetchone()
        
        is_enrolled = False
        progress = 0
        
        if 'user_id' in session:
            cursor.execute(
                'SELECT * FROM enrollments WHERE user_id = ? AND course_id = ?',
                (session['user_id'], course_id)
            )
            enrollment = cursor.fetchone()
            if enrollment:
                is_enrolled = True
                progress = enrollment['progress']
        
        conn.close()
        
        if not course:
            flash('Course not found', 'danger')
            return redirect(url_for('courses'))
        
        return render_template('course_detail.html',
                             course=course,
                             is_enrolled=is_enrolled,
                             progress=progress,
                             user_id=session.get('user_id'),
                             username=session.get('username'))
    except Exception as e:
        print(f"Course detail error: {e}")
        flash('An error occurred', 'danger')
        return redirect(url_for('courses'))

@app.route('/enroll/<int:course_id>')
@login_required
def enroll(course_id):
    try:
        user_id = session['user_id']
        conn = get_db()
        cursor = conn.cursor()
        
        # Check if course exists
        cursor.execute('SELECT id FROM courses WHERE id = ?', (course_id,))
        if not cursor.fetchone():
            flash('Course not found', 'danger')
            conn.close()
            return redirect(url_for('courses'))
        
        # Check if already enrolled
        cursor.execute(
            'SELECT id FROM enrollments WHERE user_id = ? AND course_id = ?',
            (user_id, course_id)
        )
        if cursor.fetchone():
            flash('Already enrolled in this course', 'info')
        else:
            cursor.execute(
                'INSERT INTO enrollments (user_id, course_id) VALUES (?, ?)',
                (user_id, course_id)
            )
            conn.commit()
            flash('Successfully enrolled in the course!', 'success')
        
        conn.close()
        
        return redirect(url_for('course_detail', course_id=course_id))
    except Exception as e:
        print(f"Enroll error: {e}")
        flash('An error occurred during enrollment', 'danger')
        return redirect(url_for('courses'))

@app.route('/update-progress/<int:course_id>', methods=['POST'])
@login_required
def update_progress(course_id):
    if request.method == 'POST':
        progress = request.form.get('progress', 0, type=int)
        progress = max(0, min(100, progress))  # Clamp between 0-100
        
        try:
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE enrollments SET progress = ? WHERE user_id = ? AND course_id = ?',
                (progress, session['user_id'], course_id)
            )
            conn.commit()
            conn.close()
            flash('Progress updated!', 'success')
        except Exception as e:
            print(f"Progress update error: {e}")
            flash('Failed to update progress', 'danger')
    
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/my-courses')
@login_required
def my_courses():
    try:
        user_id = session['user_id']
        conn = get_db()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT c.*, e.progress, e.enrolled_at
            FROM enrollments e 
            JOIN courses c ON e.course_id = c.id 
            WHERE e.user_id = ?
            ORDER BY e.enrolled_at DESC
        ''', (user_id,))
        courses_list = cursor.fetchall()
        
        conn.close()
        
        return render_template('my_courses.html', 
                             courses=courses_list,
                             username=session['username'])
    except Exception as e:
        print(f"My courses error: {e}")
        return render_template('my_courses.html', courses=[])

@app.route('/admin/courses')
@admin_required
def admin_courses():
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM courses ORDER BY id DESC')
        courses = cursor.fetchall()
        cursor.execute('SELECT COUNT(*) FROM users')
        user_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(*) FROM enrollments')
        enrollment_count = cursor.fetchone()[0]
        conn.close()
        
        return render_template('admin_courses.html',
                             courses=courses,
                             user_count=user_count,
                             enrollment_count=enrollment_count,
                             username=session['username'])
    except Exception as e:
        print(f"Admin courses error: {e}")
        flash('Admin access error', 'danger')
        return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html', 
                         user_id=session.get('user_id'),
                         username=session.get('username')), 404

@app.errorhandler(500)
def internal_error(error):
    print(f"500 Error: {error}")
    return render_template('500.html', 
                         user_id=session.get('user_id'),
                         username=session.get('username')), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Server starting on http://0.0.0.0:{port}")
    print(f"🔑 Admin login: admin / admin123")
    print(f"📁 Database path: {os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')}")
    app.run(host='0.0.0.0', port=port, debug=False)