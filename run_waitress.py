from waitress import serve
from zkmanager.wsgi import application
import os
import subprocess
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def start_scheduler():
    """Starts the Django APScheduler in the background."""
    print("Starting background scheduler...")
    # Use sys.executable to ensure we use the same Python environment
    subprocess.Popen([sys.executable, "manage.py", "run_sync_scheduler"])

if __name__ == '__main__':
    start_scheduler()
    
    port = os.getenv('PORT', '8000')
    print(f"Starting Waitress server on http://0.0.0.0:{port}")
    serve(application, host='0.0.0.0', port=port)
