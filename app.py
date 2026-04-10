from dotenv import load_dotenv
import os
load_dotenv()

from flask import Flask
from models import db

def create_app():
    app = Flask(__name__)
    if not os.getenv('SECRET_KEY'):
        raise RuntimeError("SECRET_KEY is not set in environment variables")
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///app.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    db.init_app(app)

    @app.template_filter('format_aed')
    def format_aed(value):
        try:
            return f"AED {float(value):,.2f}"
        except (ValueError, TypeError):
            return "AED 0.00"

    from routes import routes_bp
    app.register_blueprint(routes_bp)

    return app

app = create_app()

if __name__ == '__main__':
    app = create_app()
    port = int(os.environ.get('PORT', 5000))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ['true', '1', 't']
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
