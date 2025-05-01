from flask import Blueprint, render_template, redirect, url_for, flash, request
from .forms import RegisterForm, LoginForm
from .models import db, User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import login_user, logout_user, login_required, current_user
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer
from . import mail
from flask import current_app

auth = Blueprint('auth', __name__)


@auth.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():  # Valida o formulário quando é submetido
        # Verifica se o email já existe no banco
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            flash('Este email já está em uso. Tente outro.', 'danger')
            return redirect(url_for('auth.register'))

        # Se não houver erro, cria o usuário
        hashed_password = generate_password_hash(form.password.data, method='pbkdf2:sha256')
        new_user = User(username=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()

        flash('Conta criada com sucesso!', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', form=form)


@auth.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data
        senha = form.password.data
        user = User.query.filter_by(email=email).first()

        if not user or not check_password_hash(user.password, senha):
            flash('Email ou senha incorretos.', 'danger')
            return redirect(url_for('auth.login'))

        login_user(user, remember=True)
        return redirect(url_for('main.home'))  # Ajuste a rota para onde você quer redirecionar após login

    return render_template('login.html', form=form)


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Você saiu da conta.', 'info')
    return redirect(url_for('main.home'))  # Redireciona para a página principal após logout


def send_reset_email(user, app):
    serializer = URLSafeTimedSerializer(app.config['SECRET_KEY'])
    token = serializer.dumps(user.email, salt='reset-senha')

    link = url_for('auth.reset_token', token=token, _external=True)
    msg = Message('Recuperar senha - Letterbook',
                  sender='seuemail@gmail.com',
                  recipients=[user.email])
    msg.body = f'Clique no link para redefinir sua senha: {link}'

    with app.app_context():
        mail.send(msg)


@auth.route('/reset', methods=['GET', 'POST'])
def reset_request():
    if request.method == 'POST':
        email = request.form.get('email')
        user = User.query.filter_by(email=email).first()
        if user:
            send_reset_email(user, current_app)
            flash('Email de recuperação enviado.', 'info')
        else:
            flash('Nenhuma conta com esse email.', 'danger')
    return render_template('reset_request.html')


@auth.route('/reset/<token>', methods=['GET', 'POST'])
def reset_token(token):
    serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    try:
        email = serializer.loads(token, salt='reset-senha', max_age=3600)
    except:
        flash('Token inválido ou expirado.', 'danger')
        return redirect(url_for('auth.reset_request'))

    user = User.query.filter_by(email=email).first()
    if request.method == 'POST':
        new_password = generate_password_hash(request.form.get('password'), method='sha256')
        user.password = new_password
        db.session.commit()
        flash('Senha redefinida com sucesso!', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_token.html')


@auth.route('/forgot_password', methods=['GET', 'POST'])
def forgot_password():
    return render_template('forgot_password.html')

