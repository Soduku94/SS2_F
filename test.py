# In your main Flask app file (e.g., run.py or where app is defined)
# After app = Flask(__name__) and all app.config settings
import app

print(f"DEBUG: The SECRET_KEY being used is: {app.config.get('SECRET_KEY')}")
