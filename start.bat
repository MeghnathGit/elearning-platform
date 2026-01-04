@echo off
echo 🚀 Starting eLearning Platform...
echo.

cd /d "C:\elearning-project"

echo 📦 Installing dependencies...
pip install flask werkzeug

echo.
echo 🚀 Starting server...
echo 🌐 Open your browser to: http://localhost:5000
echo 👤 Admin login: admin / admin123
echo.

python app.py
pause