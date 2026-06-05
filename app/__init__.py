# app/__init__.py

from flask import Flask
from app.extensions import db, login_manager    # ← import from extensions


def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    app.json.sort_keys = False

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.routes.auth       import auth_bp
    from app.routes.admin      import admin_bp
    from app.routes.attendance import attendance_bp
    from app.routes.employee   import employee_bp
    from app.routes.location   import location_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(attendance_bp)
    app.register_blueprint(employee_bp)
    app.register_blueprint(location_bp)

    from app.models import Employee

    @login_manager.user_loader
    def load_user(user_id):
        return Employee.query.get(int(user_id))

    with app.app_context():
        db.create_all()

    return app