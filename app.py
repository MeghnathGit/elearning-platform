from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-123'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///elearning.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

# Database Models
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    enrollments = db.relationship('Enrollment', backref='user', lazy=True)
    courses_created = db.relationship('Course', backref='instructor', lazy=True)

class Course(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=False)
    instructor_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    enrollments = db.relationship('Enrollment', backref='course', lazy=True)
    contents = db.relationship('Content', backref='course', lazy=True)

class Content(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    content_type = db.Column(db.String(50), nullable=False)  # video, pdf, quiz
    content_url = db.Column(db.String(500), nullable=False)
    duration = db.Column(db.String(20))  # For videos
    sequence = db.Column(db.Integer, default=0)

class Enrollment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
    enrolled_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed = db.Column(db.Boolean, default=False)

# User loader for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Routes
@app.route('/')
def index():
    # Get top 6 courses
    courses = Course.query.order_by(Course.created_at.desc()).limit(6).all()
    return render_template('index.html', courses=courses)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash('Logged in successfully!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Check if user exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists', 'danger')
            return redirect(url_for('register'))
        
        # Create new user
        hashed_password = generate_password_hash(password)
        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            is_admin=False  # Default to student
        )
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))

@app.route('/courses')
def courses():
    all_courses = Course.query.all()
    enrolled_course_ids = []
    if current_user.is_authenticated:
        enrolled_course_ids = [e.course_id for e in current_user.enrollments]
    
    return render_template('courses.html', 
                          courses=all_courses, 
                          enrolled_course_ids=enrolled_course_ids)

@app.route('/course/<int:course_id>')
def course_detail(course_id):
    course = Course.query.get_or_404(course_id)
    contents = Content.query.filter_by(course_id=course_id).order_by(Content.sequence).all()
    
    is_enrolled = False
    if current_user.is_authenticated:
        enrollment = Enrollment.query.filter_by(
            user_id=current_user.id, 
            course_id=course_id
        ).first()
        is_enrolled = enrollment is not None
    
    return render_template('course_detail.html', 
                          course=course, 
                          contents=contents, 
                          is_enrolled=is_enrolled)

@app.route('/enroll/<int:course_id>')
@login_required
def enroll(course_id):
    # Check if already enrolled
    existing = Enrollment.query.filter_by(
        user_id=current_user.id, 
        course_id=course_id
    ).first()
    
    if not existing:
        enrollment = Enrollment(
            user_id=current_user.id,
            course_id=course_id
        )
        db.session.add(enrollment)
        db.session.commit()
        flash('Successfully enrolled in the course!', 'success')
    else:
        flash('You are already enrolled in this course', 'info')
    
    return redirect(url_for('course_detail', course_id=course_id))

@app.route('/my-courses')
@login_required
def my_courses():
    enrollments = Enrollment.query.filter_by(user_id=current_user.id).all()
    enrolled_courses = [enrollment.course for enrollment in enrollments]
    return render_template('my_courses.html', courses=enrolled_courses)

@app.route('/admin')
@login_required
def admin():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'danger')
        return redirect(url_for('index'))
    
    users_count = User.query.count()
    courses_count = Course.query.count()
    enrollments_count = Enrollment.query.count()
    
    return render_template('admin.html',
                          users_count=users_count,
                          courses_count=courses_count,
                          enrollments_count=enrollments_count)

@app.route('/admin/add-course', methods=['GET', 'POST'])
@login_required
def add_course():
    if not current_user.is_admin:
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        category = request.form['category']
        
        course = Course(
            title=title,
            description=description,
            category=category,
            instructor_id=current_user.id
        )
        
        db.session.add(course)
        db.session.commit()
        
        flash('Course added successfully!', 'success')
        return redirect(url_for('admin'))
    
    return render_template('add_course.html')

@app.route('/profile')
@login_required
def profile():
    user = current_user
    enrolled_courses_count = len(user.enrollments)
    return render_template('profile.html', 
                          user=user, 
                          enrolled_courses_count=enrolled_courses_count)

# Initialize database and create admin user
def init_db():
    with app.app_context():
        db.create_all()
        
        # Check if admin exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin_user = User(
                username='admin',
                email='admin@elearning.com',
                password=generate_password_hash('admin123'),
                is_admin=True
            )
            db.session.add(admin_user)
            
            # Add some sample courses
            sample_courses = [
                Course(
                    title='Python Programming Basics',
                    description='Learn Python from scratch with hands-on exercises.',
                    category='Programming',
                    instructor_id=1
                ),
                Course(
                    title='Web Development with Flask',
                    description='Build web applications using Python Flask framework.',
                    category='Web Development',
                    instructor_id=1
                ),
                Course(
                    title='Data Science Fundamentals',
                    description='Introduction to data science concepts and tools.',
                    category='Data Science',
                    instructor_id=1
                ),
                Course(
                    title='Machine Learning Basics',
                    description='Understand ML algorithms and applications.',
                    category='Artificial Intelligence',
                    instructor_id=1
                ),
                Course(
                    title='Database Management Systems',
                    description='Learn SQL and database design principles.',
                    category='Database',
                    instructor_id=1
                ),
                Course(
                    title='Cloud Computing Essentials',
                    description='Introduction to cloud platforms and services.',
                    category='Cloud Computing',
                    instructor_id=1
                )
            ]
            
            for course in sample_courses:
                db.session.add(course)
            
            db.session.commit()
            print("✅ Database initialized with admin user and sample courses!")

if __name__ == '__main__':
    init_db()
    app.run(debug=True)