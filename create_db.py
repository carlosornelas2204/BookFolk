from app import create_app
from app.models import db

app = create_app()

with app.app_context():
    db.create_all()  # Cria todas as tabelas no banco
    print("Banco de dados e tabelas criadas com sucesso!")
