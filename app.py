from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
import os
import sqlite3
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-in-production')
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=7)
app.config['SESSION_COOKIE_SECURE'] = True
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

def get_db_connection():
    database_url = os.environ.get('DATABASE_URL')
    
    if database_url and database_url.startswith('postgres://'):
        # PostgreSQL (Railway)
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
        import psycopg2
        conn = psycopg2.connect(database_url, sslmode='require')
        conn.autocommit = False
    else:
        # SQLite (Local development)
        conn = sqlite3.connect('elearning.db')
    
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
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
                instructor VARCHAR(100),
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
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        ''')
        
        # Insert default admin if not exists
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone() is None:
            hashed_pw = generate_password_hash('admin123')
            cursor.execute(
                "INSERT INTO users (username, email, password, is_admin) VALUES (%s, %s, %s, %s)",
                ('admin', 'admin@cognilearn.com', hashed_pw, True)
            )
        
        # Insert sample courses if none exist
        cursor.execute("SELECT COUNT(*) FROM courses")
        if cursor.fetchone()[0] == 0:
            sample_courses = [
                ('Python Programming Masterclass', 'Master Python from basics to advanced', 'Programming', 'Dr. Alex Johnson', 60, 'Intermediate'),
                ('Web Development Bootcamp', 'Build modern websites', 'Web Development', 'Sarah Williams', 80, 'Beginner'),
                ('Data Science Fundamentals', 'Learn data analysis and ML', 'Data Science', 'Dr. Michael Chen', 100, 'Advanced'),
                ('Cloud Computing with AWS', 'Master AWS services', 'Cloud Computing', 'James Wilson', 70, 'Intermediate'),
                ('Cybersecurity Essentials', 'Protect systems from threats', 'Security', 'Emma Rodriguez', 50, 'Beginner'),
                ('AI & Machine Learning', 'Learn AI algorithms', 'Artificial Intelligence', 'Dr. Robert Kim', 120, 'Advanced')
            ]
            
            for course in sample_courses:
                cursor.execute(
                    "INSERT INTO courses (title, description, category, instructor, duration, level) VALUES (%s, %s, %s, %s, %s, %s)",
                    course
                )
        
        conn.commit()
    except Exception as e:
        print(f"Database initialization error: {e}")
        conn.rollback()
    finally:
        conn.close()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            flash('Please login to access this page', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or not session['user'].get('is_admin'):
            flash('Admin access required', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

# =============== ROUTES ===============

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM courses ORDER BY RANDOM() LIMIT 6')
    featured = cursor.fetchall()
    
    cursor.execute('SELECT COUNT(*) FROM courses')
    total_courses = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM users')
    total_students = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM enrollments')
    total_enrollments = cursor.fetchone()[0]
    
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
    if 'user' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[3], password):
            session['user'] = {
                'id': user[0],
                'username': user[1],
                'email': user[2],
                'is_admin': user[4]
            }
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid credentials', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user' in session:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        hashed_password = generate_password_hash(password)
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT INTO users (username, email, password) VALUES (%s, %s, %s)',
                (username, email, hashed_password)
            )
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Username or email already exists', 'danger')
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    user_id = session['user']['id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT c.*, e.progress, e.enrolled_at, e.id as enrollment_id 
        FROM enrollments e 
        JOIN courses c ON e.course_id = c.id 
        WHERE e.user_id = %s
    ''', (user_id,))
    enrolled = cursor.fetchall()
    
    cursor.execute('''
        SELECT AVG(progress) as avg_progress 
        FROM enrollments 
        WHERE user_id = %s
    ''', (user_id,))
    avg_progress_result = cursor.fetchone()
    avg_progress = avg_progress_result[0] or 0
    
    cursor.execute('''
        SELECT * FROM courses 
        WHERE id NOT IN (
            SELECT course_id FROM enrollments WHERE user_id = %s
        )
        ORDER BY RANDOM() 
        LIMIT 3
    ''', (user_id,))
    featured = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         enrolled_courses=enrolled, 
                         avg_progress=avg_progress,
                         featured_courses=featured)

@app.route('/courses')
def courses():
    category = request.args.get('category', '')
    level = request.args.get('level', '')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = 'SELECT * FROM courses WHERE 1=1'
    params = []
    
    if category:
        query += ' AND category = %s'
        params.append(category)
    if level:
        query += ' AND level = %s'
        params.append(level)
    
    query += ' ORDER BY created_at DESC'
    cursor.execute(query, params)
    courses_list = cursor.fetchall()
    
    cursor.execute('SELECT DISTINCT category FROM courses ORDER BY category')
    categories = cursor.fetchall()
    
    cursor.execute('SELECT DISTINCT level FROM courses ORDER BY level')
    levels = cursor.fetchall()
    
    conn.close()
    
    return render_template('courses.html', 
                         courses=courses_list,
                         categories=categories,
                         levels=levels)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM courses WHERE id = %s', (course_id,))
    course = cursor.fetchone()
    
    is_enrolled = False
    if 'user' in session:
        cursor.execute(
            'SELECT * FROM enrollments WHERE user_id = %s AND course_id = %s',
            (session['user']['id'], course_id)
        )
        is_enrolled = bool(cursor.fetchone())
    
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
    user_id = session['user']['id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT 1 FROM enrollments WHERE user_id = %s AND course_id = %s',
        (user_id, course_id)
    )
    existing = cursor.fetchone()
    
    if not existing:
        cursor.execute(
            'INSERT INTO enrollments (user_id, course_id) VALUES (%s, %s)',
            (user_id, course_id)
        )
        flash('Successfully enrolled in the course!', 'success')
    else:
        flash('You are already enrolled in this course', 'info')
    
    conn.commit()
    conn.close()
    
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/update_progress/<int:enrollment_id>', methods=['POST'])
@login_required
def update_progress(enrollment_id):
    progress = request.form.get('progress', '0')
    
    try:
        progress = int(progress)
        if progress < 0 or progress > 100:
            raise ValueError
    except:
        flash('Invalid progress value', 'danger')
        return redirect(url_for('dashboard'))
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT * FROM enrollments WHERE id = %s AND user_id = %s',
        (enrollment_id, session['user']['id'])
    )
    enrollment = cursor.fetchone()
    
    if not enrollment:
        flash('Enrollment not found', 'danger')
        conn.close()
        return redirect(url_for('dashboard'))
    
    cursor.execute(
        'UPDATE enrollments SET progress = %s WHERE id = %s',
        (progress, enrollment_id)
    )
    
    if progress == 100:
        cursor.execute(
            'UPDATE enrollments SET completed_at = CURRENT_TIMESTAMP WHERE id = %s',
            (enrollment_id,)
        )
    
    conn.commit()
    conn.close()
    
    flash('Progress updated successfully!', 'success')
    return redirect(url_for('dashboard'))

@app.route('/admin')
@admin_required
def admin():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT COUNT(*) FROM users')
    users = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM courses')
    courses = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(*) FROM enrollments')
    enrollments = cursor.fetchone()[0]
    
    stats = {
        'users': users,
        'courses': courses,
        'enrollments': enrollments
    }
    
    cursor.execute('SELECT * FROM users ORDER BY created_at DESC LIMIT 10')
    recent_users = cursor.fetchall()
    
    cursor.execute('SELECT * FROM courses ORDER BY created_at DESC LIMIT 10')
    recent_courses = cursor.fetchall()
    
    conn.close()
    
    return render_template('admin.html',
                         stats=stats,
                         recent_users=recent_users,
                         recent_courses=recent_courses)

@app.route('/admin/add_course', methods=['GET', 'POST'])
@admin_required
def add_course():
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        instructor = request.form.get('instructor', 'Admin')
        duration = request.form.get('duration', '40')
        level = request.form.get('level', 'Beginner')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO courses (title, description, category, instructor, duration, level)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (title, description, category, instructor, duration, level))
        conn.commit()
        conn.close()
        
        flash('Course added successfully!', 'success')
        return redirect(url_for('admin'))
    
    return render_template('add_course.html')

@app.route('/profile')
@login_required
def profile():
    user_id = session['user']['id']
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cursor.fetchone()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as enrolled_count,
            AVG(progress) as avg_progress,
            SUM(CASE WHEN progress = 100 THEN 1 ELSE 0 END) as completed_count
        FROM enrollments 
        WHERE user_id = %s
    ''', (user_id,))
    stats = cursor.fetchone()
    
    conn.close()
    
    return render_template('profile.html', user=user, stats=stats)

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
    # Initialize database
    init_db()
    
    # Get port from environment (Railway provides this)
    port = int(os.environ.get('PORT', 5000))
    
    # Run the app
    app.run(host='0.0.0.0', port=port, debug=False)