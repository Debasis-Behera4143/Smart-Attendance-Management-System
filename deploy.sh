#!/bin/bash

# Quick deployment scripts for different platforms

echo "🚀 Smart Attendance System - Deployment Helper"
echo "================================================"
echo ""
echo "Choose deployment platform:"
echo "1. Streamlit Cloud (Recommended - FREE)"
echo "2. Hugging Face Spaces (FREE)"
echo "3. Render.com (FREE)"
echo "4. Railway.app (FREE with limits)"
echo "5. Docker (Local)"
echo "6. Flask Local Server"
echo ""
read -p "Enter choice (1-6): " choice

case $choice in
  1)
    echo ""
    echo "📱 Streamlit Cloud Deployment"
    echo "=============================="
    echo "1. Go to: https://share.streamlit.io"
    echo "2. Sign in with GitHub"
    echo "3. Click 'New app'"
    echo "4. Repository: Smart-Attendance-System"
    echo "5. Branch: main"
    echo "6. Main file path: streamlit_app.py"
    echo "7. Click 'Deploy!'"
    echo ""
    echo "✅ Your app will be live in 2-3 minutes!"
    ;;
  
  2)
    echo ""
    echo "🤗 Hugging Face Spaces Deployment"
    echo "=================================="
    echo "Follow these steps:"
    echo ""
    echo "1. Create account at https://huggingface.co"
    echo "2. Create new Space (select Streamlit SDK)"
    echo "3. Clone the Space repository:"
    echo "   git clone https://huggingface.co/spaces/YOUR-USERNAME/smart-attendance"
    echo "4. Copy files:"
    echo "   cp streamlit_app.py YOUR-SPACE/app.py"
    echo "   cp requirements-streamlit.txt YOUR-SPACE/requirements.txt"
    echo "   cp -r src models YOUR-SPACE/"
    echo "5. Create README.md with Space config"
    echo "6. Push to Hugging Face"
    echo ""
    ;;
  
  3)
    echo ""
    echo "🚂 Render.com Deployment"
    echo "========================"
    echo "1. Go to: https://render.com"
    echo "2. Connect GitHub repository"
    echo "3. Create new Web Service"
    echo "4. Build Command: pip install -r requirements.txt"
    echo "5. Start Command: python web/wsgi.py"
    echo "6. Add environment variables (see .env.example)"
    echo "7. Deploy!"
    echo ""
    ;;
  
  4)
    echo ""
    echo "🚆 Railway.app Deployment"
    echo "========================="
    echo "1. Go to: https://railway.app"
    echo "2. Sign up with GitHub"
    echo "3. New Project → Deploy from GitHub"
    echo "4. Select Smart-Attendance-System"
    echo "5. Add environment variables"
    echo "6. Deploy automatically!"
    echo ""
    ;;
  
  5)
    echo ""
    echo "🐳 Docker Deployment"
    echo "===================="
    echo "Starting Docker containers..."
    
    if command -v docker &> /dev/null; then
      docker-compose up -d
      echo "✅ Containers started!"
      echo ""
      echo "Access your applications:"
      echo "- Streamlit: http://localhost:8501"
      echo "- Flask: http://localhost:8080"
      echo ""
      echo "To stop: docker-compose down"
    else
      echo "❌ Docker not found! Please install Docker first."
      echo "Visit: https://docs.docker.com/get-docker/"
    fi
    ;;
  
  6)
    echo ""
    echo "🌐 Flask Local Server"
    echo "====================="
    echo "Starting Flask application..."
    
    # Activate virtual environment if exists
    if [ -d ".venv" ]; then
      source .venv/bin/activate || . .venv/Scripts/activate
    fi
    
    # Install requirements
    pip install -r requirements.txt
    
    # Run Flask app
    python web/wsgi.py
    ;;
  
  *)
    echo "Invalid choice!"
    ;;
esac
