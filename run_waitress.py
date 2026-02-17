from waitress import serve
from zkmanager.wsgi import application
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

if __name__ == '__main__':
    port = os.getenv('PORT', '8000')
    print(f"Starting Waitress server on http://0.0.0.0:{port}")
    serve(application, host='0.0.0.0', port=port)
