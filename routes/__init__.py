"""Register all route blueprints."""


def register_routes(app):
    from .auth import auth_bp
    from .secrets import secrets_bp
    from .backup_routes import backup_bp
    from .api import api_bp
    from .settings import settings_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(secrets_bp)
    app.register_blueprint(backup_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(settings_bp)
