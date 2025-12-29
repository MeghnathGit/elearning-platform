#!/usr/bin/env python3
"""
Setup script for E-Learning Platform
Run: python setup.py
"""

import os
import sys
import sqlite3
from werkzeug.security import generate_password_hash

def setup_project():
    print("🚀 Setting up E-Learning Platform...")
    
    # Create necessary folders
    folders = ['instance', 'static/css', 'static/js', 'static/images', 'templates']
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"✅ Created folder: {folder}")
    
    # Create database
    print("\n📦 Setting up database...")
    try:
        conn = sqlite3.connect('instance/elearning.db')
        c = conn.cursor()
        
        # Drop existing tables (if any)
        c.execute("DROP TABLE IF EXISTS enrollments")
        c.execute("DROP TABLE IF EXISTS courses")
        c.execute("DROP TABLE IF EXISTS users")
        
        # Create tables
        c.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password TEXT NOT NULL,
                is_admin BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        c.execute('''
            CREATE TABLE courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT,
                category TEXT,
                instructor_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (instructor_id) REFERENCES users(id)
            )
        ''')
        
        c.execute('''
            CREATE TABLE enrollments (
                user_id INTEGER,
                course_id INTEGER,
                enrolled_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                progress INTEGER DEFAULT 0,
                PRIMARY KEY (user_id, course_id),
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (course_id) REFERENCES courses(id)
            )
        ''')
        
        # Insert admin user
        hashed_pw = generate_password_hash('admin123')
        c.execute("INSERT INTO users (username, email, password, is_admin) VALUES (?, ?, ?, ?)",
                  ('admin', 'admin@elearning.com', hashed_pw, 1))
        
        # Insert sample courses
        sample_courses = [
            ('Python Programming Masterclass', 'Learn Python from scratch to advanced level with hands-on projects', 'Programming', 1),
            ('Web Development Bootcamp', 'Build modern websites with HTML, CSS, JavaScript and Flask', 'Web Development', 1),
            ('Data Science Fundamentals', 'Master data analysis, visualization and machine learning basics', 'Data Science', 1),
            ('Mobile App Development', 'Create cross-platform mobile apps with Flutter', 'Mobile Development', 1),
            ('Cloud Computing with AWS', 'Learn cloud deployment, services and infrastructure', 'Cloud Computing', 1),
            ('Cybersecurity Essentials', 'Protect systems and networks from cyber threats', 'Cybersecurity', 1)
        ]
        
        c.executemany("INSERT INTO courses (title, description, category, instructor_id) VALUES (?, ?, ?, ?)", 
                     sample_courses)
        
        conn.commit()
        conn.close()
        print("✅ Database setup completed successfully!")
        
    except Exception as e:
        print(f"❌ Database setup failed: {e}")
        return False
    
    # Create basic static files
    print("\n🎨 Creating static files...")
    
    # Create minimal CSS
    css_content = """
/* Basic styles */
body { font-family: Arial, sans-serif; padding-top: 70px; }
.navbar { background: linear-gradient(135deg, #3a0ca3 0%, #4361ee 100%); }
.btn-primary { background: #4361ee; border: none; }
.card { border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
"""
    
    with open('static/css/style.css', 'w') as f:
        f.write(css_content)
    
    # Create minimal JS
    js_content = """
// Basic JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('E-Learning Platform loaded');
    
    // Theme toggle
    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        themeToggle.addEventListener('click', function() {
            document.body.classList.toggle('dark-mode');
        });
    }
});
"""
    
    with open('static/js/main.js', 'w') as f:
        f.write(js_content)
    
    print("✅ Static files created successfully!")
    
    # Create requirements.txt if not exists
    if not os.path.exists('requirements.txt'):
        with open('requirements.txt', 'w') as f:
            f.write("""Flask==2.3.3
Werkzeug==2.3.7
gunicorn==20.1.0
itsdangerous==2.1.2""")
    
    print("\n🎉 Setup completed successfully!")
    print("\n📋 NEXT STEPS:")
    print("1. Install dependencies: pip install -r requirements.txt")
    print("2. Run the app: python app.py")
    print("3. Open browser: http://localhost:5000")
    print("4. Login with: admin / admin123")
    
    return True

if __name__ == '__main__':
    setup_project()