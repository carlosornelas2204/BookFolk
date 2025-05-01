📚 BookFolk
O BookFolk é uma aplicação web desenvolvida com Python e Flask, projetada para gerenciar e exibir informações relacionadas a livros. O projeto utiliza HTML e CSS para a interface do usuário e inclui scripts para a criação e gerenciamento do banco de dados.​

🚀 Tecnologias Utilizadas
Python

Flask

HTML

CSS​

📁 Estrutura do Projeto
bash
Copiar
Editar

BookFolk/
├── app/                 # Diretório principal da aplicação Flask
├── create_db.py         # Script para criação do banco de dados
├── manage.py            # Script para gerenciamento da aplicação
├── run.py               # Script para iniciar o servidor Flask
└── .idea/               # Configurações do ambiente de desenvolvimento (gerado pelo IDE)
⚙️ Como Executar o Projeto
Clone o repositório:​

bash
Copiar
Editar
git clone https://github.com/carlosornelas2204/BookFolk.git
cd BookFolk
Crie e ative um ambiente virtual (opcional, mas recomendado):​

bash
Copiar
Editar
python -m venv venv
source venv/bin/activate  # No Windows: venv\Scripts\activate
Instale as dependências necessárias:​

bash
Copiar
Editar
pip install -r requirements.txt
Crie o banco de dados:​

bash
Copiar
Editar
python create_db.py
Inicie o servidor Flask:​

bash
Copiar
Editar
python run.py
Acesse a aplicação no navegador:​

arduino
Copiar
Editar
http://localhost:5000
📄 Licença
