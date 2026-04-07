from flask import Flask
from models import db
import os

def create_app():
    app = Flask(__name__)
    secret_key = os.environ.get('SECRET_KEY')
    if not secret_key:
        raise ValueError("No SECRET_KEY set for Flask application. Did you forget to add it to your environment variables?")
    app.config['SECRET_KEY'] = secret_key
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
