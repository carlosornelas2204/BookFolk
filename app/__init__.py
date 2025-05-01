from flask import Flask, render_template
from flask_login import LoginManager
from flask_mail import Mail
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Instâncias globais
db = SQLAlchemy()
migrate = Migrate()
mail = Mail()


def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = 'minha_chave_secreta'

    # Configurações otimizadas do SQLite
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///letterbook.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'connect_args': {
            'timeout': 30,
            'check_same_thread': False  # Apenas para desenvolvimento!
        }
    }

    # Inicializando as extensões com a app
    db.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)

    # Inicializando o LoginManager
    login_manager = LoginManager()
    login_manager.login_view = 'auth.login'
    login_manager.init_app(app)

    # Carregamento do usuário
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Registre os blueprints
    from .routes import main
    app.register_blueprint(main)

    from .auth import auth
    app.register_blueprint(auth)

    # Configuração de e-mail (mantido igual)
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'seuemail@gmail.com'
    app.config['MAIL_PASSWORD'] = 'sua_senha_de_app'

    # Configuração adicional para garantir commits rápidos
    @app.teardown_request
    def teardown_request(exception=None):
        if exception:
            db.session.rollback()
        db.session.remove()

    @app.errorhandler(403)
    def forbidden_error(error):
        return render_template('403.html', error=error), 403

    return app

