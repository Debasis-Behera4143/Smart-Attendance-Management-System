# Quick Deployment Helper for Windows
# Smart Attendance System

Write-Host "🚀 Smart Attendance System - Deployment Helper" -ForegroundColor Cyan
Write-Host "================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Choose deployment platform:" -ForegroundColor Yellow
Write-Host "1. Streamlit Cloud (Recommended - FREE)"
Write-Host "2. Hugging Face Spaces (FREE)"
Write-Host "3. Render.com (FREE)"
Write-Host "4. Railway.app (FREE with limits)"
Write-Host "5. Docker (Local)"
Write-Host "6. Flask Local Server"
Write-Host "7. Streamlit Local Server"
Write-Host ""

$choice = Read-Host "Enter choice (1-7)"

switch ($choice) {
    "1" {
        Write-Host ""
        Write-Host "📱 Streamlit Cloud Deployment" -ForegroundColor Green
        Write-Host "=============================="
        Write-Host "1. Go to: https://share.streamlit.io"
        Write-Host "2. Sign in with GitHub"
        Write-Host "3. Click 'New app'"
        Write-Host "4. Repository: Smart-Attendance-System"
        Write-Host "5. Branch: main"
        Write-Host "6. Main file path: streamlit_app.py"
        Write-Host "7. Click 'Deploy!'"
        Write-Host ""
        Write-Host "✅ Your app will be live in 2-3 minutes!" -ForegroundColor Green
        Write-Host ""
        Write-Host "Opening Streamlit Cloud..." -ForegroundColor Cyan
        Start-Process "https://share.streamlit.io"
    }
    
    "2" {
        Write-Host ""
        Write-Host "🤗 Hugging Face Spaces" -ForegroundColor Green
        Write-Host "======================="
        Write-Host "Opening Hugging Face..." -ForegroundColor Cyan
        Start-Process "https://huggingface.co/spaces"
        Write-Host ""
        Write-Host "Steps:"
        Write-Host "1. Create new Space (Streamlit SDK)"
        Write-Host "2. Upload streamlit_app.py as app.py"
        Write-Host "3. Upload requirements-streamlit.txt as requirements.txt"
        Write-Host "4. Upload src/ and models/ folders"
    }
    
    "3" {
        Write-Host ""
        Write-Host "🚂 Render.com" -ForegroundColor Green
        Write-Host "=============="
        Write-Host "Opening Render.com..." -ForegroundColor Cyan
        Start-Process "https://render.com"
    }
    
    "4" {
        Write-Host ""
        Write-Host "🚆 Railway.app" -ForegroundColor Green
        Write-Host "==============="
        Write-Host "Opening Railway..." -ForegroundColor Cyan
        Start-Process "https://railway.app"
    }
    
    "5" {
        Write-Host ""
        Write-Host "🐳 Docker Deployment" -ForegroundColor Green
        Write-Host "===================="
        
        if (Get-Command docker -ErrorAction SilentlyContinue) {
            Write-Host "Starting Docker containers..." -ForegroundColor Cyan
            docker-compose up -d
            Write-Host ""
            Write-Host "✅ Containers started!" -ForegroundColor Green
            Write-Host ""
            Write-Host "Access your applications:" -ForegroundColor Yellow
            Write-Host "- Streamlit: http://localhost:8501"
            Write-Host "- Flask: http://localhost:8080"
            Write-Host ""
            Write-Host "To stop: docker-compose down" -ForegroundColor Gray
        } else {
            Write-Host "❌ Docker not found!" -ForegroundColor Red
            Write-Host "Install Docker Desktop: https://www.docker.com/products/docker-desktop"
            Start-Process "https://www.docker.com/products/docker-desktop"
        }
    }
    
    "6" {
        Write-Host ""
        Write-Host "🌐 Flask Local Server" -ForegroundColor Green
        Write-Host "====================="
        
        # Activate virtual environment
        if (Test-Path ".venv\Scripts\Activate.ps1") {
            Write-Host "Activating virtual environment..." -ForegroundColor Cyan
            & .venv\Scripts\Activate.ps1
        }
        
        Write-Host "Installing requirements..." -ForegroundColor Cyan
        pip install -r requirements.txt
        
        Write-Host ""
        Write-Host "Starting Flask server..." -ForegroundColor Cyan
        Write-Host "Access at: http://localhost:8080" -ForegroundColor Yellow
        Write-Host ""
        python web/wsgi.py
    }
    
    "7" {
        Write-Host ""
        Write-Host "📱 Streamlit Local Server" -ForegroundColor Green
        Write-Host "=========================="
        
        # Activate virtual environment
        if (Test-Path ".venv\Scripts\Activate.ps1") {
            Write-Host "Activating virtual environment..." -ForegroundColor Cyan
            & .venv\Scripts\Activate.ps1
        }
        
        Write-Host "Installing requirements..." -ForegroundColor Cyan
        pip install -r requirements-streamlit.txt
        
        Write-Host ""
        Write-Host "Starting Streamlit server..." -ForegroundColor Cyan
        Write-Host "Access at: http://localhost:8501" -ForegroundColor Yellow
        Write-Host ""
        streamlit run streamlit_app.py
    }
    
    default {
        Write-Host "Invalid choice!" -ForegroundColor Red
    }
}
