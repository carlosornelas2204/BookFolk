from .models import ClubMessage, ClubInvite, RecommendationHistory
import requests
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    abort
)
from flask_login import login_required, current_user
from .models import db, User, Club, ClubMember, ClubTopic, Book, Review
from werkzeug.security import generate_password_hash
import re
from datetime import datetime, timedelta
import random

main = Blueprint('main', __name__)

def is_password_strong(password):
    if len(password) < 8:
        return False
    if not re.search("[a-z]", password):
        return False
    if not re.search("[A-Z]", password):
        return False
    if not re.search("[0-9]", password):
        return False
    return True

# Função para buscar livros na API
def get_books_from_api(query):
    url = f"https://openlibrary.org/search.json?q={query}&limit=10"
    response = requests.get(url)
    data = response.json()
    return data.get('docs', [])


@main.route('/')
@login_required
def home():
    # Estatísticas
    last_week = datetime.utcnow() - timedelta(days=7)
    current_month = datetime.utcnow().month
    current_year = datetime.utcnow().year

    # Livros lidos na semana
    weekly_books = Review.query.filter(
        Review.user_id == current_user.id,
        Review.date_rated >= last_week
    ).count()

    # Gênero mais lido
    most_read_genre = db.session.query(
        Book.genre,
        db.func.count(Review.id).label('count')
    ).join(Review).filter(
        Review.user_id == current_user.id
    ).group_by(Book.genre).order_by(db.desc('count')).first()

    # Autor mais lido
    most_read_author = db.session.query(
        Book.author,
        db.func.count(Review.id).label('count')
    ).join(Review).filter(
        Review.user_id == current_user.id
    ).group_by(Book.author).order_by(db.desc('count')).first()

    # Atividades recentes
    recent_reviews = db.session.query(Review, Book).join(Book).filter(
        Review.user_id == current_user.id
    ).order_by(Review.date_rated.desc()).limit(3).all()

    # Dados mensais - últimos 6 meses
    month_labels = []
    books_per_month = []

    for i in range(6):
        month = current_month - i
        year = current_year
        if month < 1:
            month += 12
            year -= 1

        month_name = datetime(year, month, 1).strftime('%b/%Y')
        count = Review.query.filter(
            Review.user_id == current_user.id,
            db.func.extract('month', Review.date_rated) == month,
            db.func.extract('year', Review.date_rated) == year
        ).count()

        month_labels.insert(0, month_name)
        books_per_month.insert(0, count)

    return render_template('home.html',
                           weekly_books=weekly_books,
                           most_read_genre=most_read_genre,
                           most_read_author=most_read_author,
                           recent_reviews=recent_reviews,
                           month_labels=month_labels,
                           month_data=books_per_month)


@main.route('/recommend')
@login_required
def recommend():
    # Passo 1: Buscar os livros que o usuário já leu
    user_reviews = Review.query.filter_by(user_id=current_user.id).all()
    read_books = [review.book for review in user_reviews]
    read_book_ids = [book.id for book in read_books]

    if not read_books:
        # Se não leu nada, recomenda um livro aleatório do banco
        random_book = Book.query.order_by(db.func.random()).first()
        return render_template('recommendation.html', book=random_book)

    # Passo 2: Pegar os últimos 5 livros recomendados (para evitar repetição)
    last_recommended = db.session.query(RecommendationHistory.book_id) \
        .filter_by(user_id=current_user.id) \
        .order_by(RecommendationHistory.created_at.desc()) \
        .limit(5) \
        .all()
    excluded_ids = [book_id for (book_id,) in last_recommended]

    # Passo 3: Buscar recomendações baseadas nos interesses
    recommendations = []

    # Estratégia 1: Livros do mesmo autor
    authors = list({book.author for book in read_books if book.author})
    for author in authors[:2]:  # Limita a 2 autores
        books = Book.query.filter(
            Book.author == author,
            Book.id.notin_(read_book_ids),
            Book.id.notin_(excluded_ids)
        ).limit(3).all()
        recommendations.extend(books)

    # Estratégia 2: Livros com palavras similares no título
    title_words = set()
    for book in read_books:
        title_words.update(book.title.split()[:3])

    for word in list(title_words)[:3]:  # Limita a 3 palavras-chave
        books = Book.query.filter(
            Book.title.ilike(f'%{word}%'),
            Book.id.notin_(read_book_ids),
            Book.id.notin_(excluded_ids)
        ).limit(3).all()
        recommendations.extend(books)

    # Passo 4: Selecionar uma recomendação
    if recommendations:
        recommended_book = random.choice(recommendations)
    else:
        # Fallback: livro aleatório não lido
        recommended_book = Book.query.filter(
            Book.id.notin_(read_book_ids),
            Book.id.notin_(excluded_ids)
        ).order_by(db.func.random()).first()

    # Registrar a recomendação no histórico
    if recommended_book:
        new_recommendation = RecommendationHistory(
            user_id=current_user.id,
            book_id=recommended_book.id
        )
        db.session.add(new_recommendation)
        db.session.commit()

    return render_template('recommendation.html', book=recommended_book)


@main.route('/reviews')
@login_required
def reviews():
    # Mantém a função original do home (agora chamada de reviews)
    query = request.args.get('query', '')
    min_rating = request.args.get('min_rating', 0, type=float)

    books_query = db.session.query(
        Book,
        db.func.avg(Review.rating).label('average_rating'),
        db.func.count(Review.id).label('review_count')
    ).join(Review).group_by(Book.id)

    # Aplicar filtros
    if query:
        books_query = books_query.filter(
            Book.title.ilike(f'%{query}%') |
            Book.author.ilike(f'%{query}%')
        )

    if min_rating > 0:
        books_query = books_query.having(
            db.func.avg(Review.rating) >= min_rating
        )

    # Ordenar por melhor avaliação
    books_data = books_query.order_by(
        db.desc('average_rating'),
        db.desc('review_count')
    ).all()

    return render_template('reviews.html', books_data=books_data)

# Buscar Livros na API
@main.route('/books')
@login_required
def books():
    query = request.args.get('query', '')
    page = request.args.get('page', 1, type=int)
    per_page = 10  # Itens por página

    if query:
        # Busca na API com paginação
        url = f"https://openlibrary.org/search.json?q={query}&limit={per_page}&page={page}"
        response = requests.get(url)
        data = response.json()

        # Extrai informações básicas para mostrar rápido
        books = [{
            'key': book.get('key'),
            'title': book.get('title'),
            'author': book.get('author_name', ['Desconhecido'])[0] if book.get('author_name') else 'Desconhecido',
            'cover_i': book.get('cover_i')
        } for book in data.get('docs', [])]

        total_results = data.get('numFound', 0)
    else:
        books = []
        total_results = 0

    return render_template(
        'books.html',
        books=books,
        query=query,
        page=page,
        per_page=per_page,
        total_results=total_results
    )


# Marcar como lido e avaliar
@main.route('/mark_read', methods=['POST'])
@login_required
def mark_read():
    book_data = {
        'open_library_id': request.form.get('book_id'),
        'title': request.form.get('title'),
        'author': request.form.get('author'),
        'genre': request.form.get('genre'),
        'cover_i': request.form.get('cover_i'),
        'isbn': request.form.get('isbn', '')
    }

    # Verifica se o livro já existe no banco
    book = Book.query.filter_by(open_library_id=book_data['open_library_id']).first()
    if not book:
        book = Book(**book_data)
        db.session.add(book)
        db.session.commit()

    return redirect(url_for('main.rate_book', book_id=book.id))


# Formulário de avaliação
@main.route('/rate_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def rate_book(book_id):
    book = Book.query.get_or_404(book_id)

    # Verifica se já existe avaliação do usuário para este livro
    review = Review.query.filter_by(
        user_id=current_user.id,
        book_id=book.id
    ).first()

    if request.method == 'POST':
        rating = int(request.form.get('rating'))
        comment = request.form.get('comment', '')

        if review:
            # Atualiza avaliação existente
            review.rating = rating
            review.comment = comment
            flash('Avaliação atualizada com sucesso!', 'success')
        else:
            # Cria nova avaliação
            review = Review(
                user_id=current_user.id,
                book_id=book.id,
                rating=rating,
                comment=comment,
                read=True
            )
            db.session.add(review)
            flash('Avaliação salva com sucesso!', 'success')

        db.session.commit()
        return redirect(url_for('main.read_books'))

    # Se GET, mostra o formulário com dados existentes (se houver)
    return render_template('rate_book.html', book=book, review=review)


# Livros lidos pelo usuário
@main.route('/read_books')
@login_required
def read_books():
    # Busca todas as avaliações do usuário, ordenadas por data
    reviews = Review.query.filter_by(
        user_id=current_user.id
    ).order_by(Review.date_rated.desc()).all()

    return render_template('read_books.html', reviews=reviews)


@main.route('/book/<int:book_id>')
@login_required
def book_detail(book_id):
    book = Book.query.get_or_404(book_id)

    # Calcula média e contagem de avaliações
    avg_rating = db.session.query(
        db.func.avg(Review.rating)
    ).filter_by(book_id=book.id).scalar()

    review_count = db.session.query(
        db.func.count(Review.id)
    ).filter_by(book_id=book.id).scalar()

    # Pega as últimas avaliações
    reviews = Review.query.filter_by(
        book_id=book.id
    ).order_by(Review.date_rated.desc()).limit(5).all()

    return render_template(
        'book_detail.html',
        book=book,
        avg_rating=avg_rating,
        review_count=review_count,
        reviews=reviews
    )


@main.route('/clubs')
@login_required
def clubs():
    # Clubes que o usuário é dono ou membro
    user_clubs = Club.query.join(ClubMember).filter(
        (Club.owner_id == current_user.id) |
        (ClubMember.user_id == current_user.id)
    ).distinct().all()

    return render_template('clubs.html', clubs=user_clubs)


@main.route('/clubs/create', methods=['GET', 'POST'])
@login_required
def create_club():
    if request.method == 'POST':
        name = request.form.get('name')
        max_members = int(request.form.get('max_members', 2))

        if max_members < 2:
            flash('O clube deve ter pelo menos 2 membros', 'danger')
            return redirect(url_for('main.create_club'))

        # Create and commit the club first
        club = Club(
            name=name,
            owner_id=current_user.id,
            max_members=max_members
        )
        db.session.add(club)
        db.session.commit()  # This generates the club.id

        # Now create the member with the valid club_id
        member = ClubMember(
            club_id=club.id,  # Now club.id exists
            user_id=current_user.id
        )
        db.session.add(member)
        db.session.commit()

        flash('Clube criado com sucesso!', 'success')
        return redirect(url_for('main.club_detail', club_id=club.id))

    return render_template('create_club.html')


@main.route('/clubs/<int:club_id>')
@login_required
def club_detail(club_id):
    club = Club.query.get_or_404(club_id)
    is_owner = club.owner_id == current_user.id
    is_member = ClubMember.query.filter_by(
        club_id=club.id,
        user_id=current_user.id
    ).first() is not None

    if not is_owner and not is_member:
        abort(403)

    members = ClubMember.query.filter_by(club_id=club.id).all()
    topics = ClubTopic.query.filter_by(club_id=club.id).order_by(ClubTopic.order).all()

    # Verifica se o usuário atual já escolheu um livro
    user_has_chosen = ClubMember.query.filter_by(
        club_id=club.id,
        user_id=current_user.id
    ).filter(ClubMember.book_id.isnot(None)).first() is not None

    # Verifica se TODOS os membros já escolheram livros (para o dono iniciar a leitura)
    all_members_have_chosen = all(member.book_id is not None for member in members)

    return render_template('club_detail.html',
                         club=club,
                         is_owner=is_owner,
                         is_member=is_member,
                         user_has_chosen=user_has_chosen,
                         all_members_have_chosen=all_members_have_chosen,
                         members=members,
                         topics=topics)


@main.route('/clubs/<int:club_id>/invite', methods=['POST'])
@login_required
def invite_to_club(club_id):
    club = Club.query.get_or_404(club_id)

    if club.owner_id != current_user.id:
        abort(403, description="Apenas o dono do clube pode convidar membros")

    username = request.form.get('username')
    user = User.query.filter_by(username=username).first()

    if not user:
        flash('Usuário não encontrado', 'danger')
        return redirect(url_for('main.club_detail', club_id=club.id))

    # Verifica se já é membro
    existing_member = ClubMember.query.filter_by(
        club_id=club.id,
        user_id=user.id
    ).first()

    if existing_member:
        flash('Este usuário já é membro do clube', 'warning')
        return redirect(url_for('main.club_detail', club_id=club.id))

    # Verifica se já existe convite pendente
    existing_invite = ClubInvite.query.filter_by(
        club_id=club.id,
        user_id=user.id,
        status='pending'
    ).first()

    if existing_invite:
        flash('Já existe um convite pendente para este usuário', 'warning')
        return redirect(url_for('main.club_detail', club_id=club.id))

    # Cria o convite
    invite = ClubInvite(
        club_id=club.id,
        user_id=user.id,
        sender_id=current_user.id,
        status='pending'
    )
    db.session.add(invite)
    db.session.commit()

    flash(f'Convite enviado para {username}!', 'success')
    return redirect(url_for('main.club_detail', club_id=club.id))


@main.route('/clubs/<int:club_id>/choose_book', methods=['GET', 'POST'])
@login_required
def choose_book(club_id):
    club = Club.query.get_or_404(club_id)
    member = ClubMember.query.filter_by(
        club_id=club.id,
        user_id=current_user.id
    ).first()

    if not member:
        abort(403, description="Você não é membro deste clube")

    if club.current_phase != 'forming':
        flash('A fase de escolha de livros já terminou', 'warning')
        return redirect(url_for('main.club_detail', club_id=club.id))

    if request.method == 'POST':
        # Se for uma submissão de livro escolhido
        if 'book_id' in request.form:
            book_id = request.form.get('book_id')
            book = Book.query.get(book_id)

            if not book:
                flash('Livro não encontrado', 'danger')
                return redirect(url_for('main.club_detail', club_id=club.id))

            member.book_id = book.id
            db.session.commit()
            flash(f'Você escolheu "{book.title}" para o clube!', 'success')
            return redirect(url_for('main.club_detail', club_id=club.id))

        # Se for uma busca de livros
        elif 'book_query' in request.form:
            query = request.form.get('book_query')
            url = f"https://openlibrary.org/search.json?q={query}&limit=5"
            response = requests.get(url)
            data = response.json()

            search_results = []
            for book_data in data.get('docs', []):
                # Verifica se o livro já existe no banco
                book = Book.query.filter_by(open_library_id=book_data.get('key').split('/')[-1]).first()
                if not book:
                    book = Book(
                        open_library_id=book_data.get('key').split('/')[-1],
                        title=book_data.get('title', 'Título desconhecido'),
                        author=', '.join(book_data.get('author_name', ['Autor desconhecido'])),
                        cover_i=book_data.get('cover_i')
                    )
                    db.session.add(book)
                    db.session.commit()

                search_results.append(book)

            # Renderiza a página com os resultados
            is_owner = club.owner_id == current_user.id
            members = ClubMember.query.filter_by(club_id=club.id).all()
            topics = ClubTopic.query.filter_by(club_id=club.id).order_by(ClubTopic.order).all()

            return render_template('club_detail.html',
                                   club=club,
                                   is_owner=is_owner,
                                   is_member=True,
                                   user_has_chosen=member.book_id is not None,
                                   members=members,
                                   topics=topics,
                                   search_results=search_results)

    return redirect(url_for('main.club_detail', club_id=club.id))


@main.route('/clubs/<int:club_id>/start_reading', methods=['POST'])
@login_required
def start_reading(club_id):
    club = Club.query.get_or_404(club_id)

    if club.owner_id != current_user.id:
        abort(403)

    if club.current_phase != 'forming':
        flash('O clube já começou a ler', 'warning')
        return redirect(url_for('main.club_detail', club_id=club.id))

    # Verifica se todos escolheram livros
    members = ClubMember.query.filter_by(club_id=club.id).all()
    if any(member.book_id is None for member in members):
        flash('Todos os membros devem escolher um livro primeiro', 'danger')
        return redirect(url_for('main.club_detail', club_id=club.id))

    # Sorteia a ordem de leitura
    books = [member.book for member in members]
    random.shuffle(books)

    # Cria os tópicos com o ciclo atual do clube
    for i, book in enumerate(books, start=1):
        topic = ClubTopic(
            club_id=club.id,
            book_id=book.id,
            order=i,
            cycle=club.current_cycle  # Usa o ciclo atual do clube
        )
        db.session.add(topic)

    club.current_phase = 'reading'
    db.session.commit()

    flash(f'Ciclo {club.current_cycle} iniciado! Ordem de leitura definida.', 'success')
    return redirect(url_for('main.club_detail', club_id=club.id))


@main.route('/clubs/<int:club_id>/topic/<int:topic_id>')
@login_required
def club_topic(club_id, topic_id):
    club = Club.query.get_or_404(club_id)
    topic = ClubTopic.query.get_or_404(topic_id)
    is_member = ClubMember.query.filter_by(
        club_id=club_id,
        user_id=current_user.id
    ).first()

    if not is_member:
        abort(403, description="Você precisa ser membro para acessar esta discussão")

    messages = ClubMessage.query.filter_by(topic_id=topic.id).order_by(ClubMessage.sent_at).all()

    return render_template('club_topic.html',
                           club=club,
                           topic=topic,
                           messages=messages)


@main.route('/clubs/<int:club_id>/topic/<int:topic_id>/message', methods=['POST'])
@login_required
def send_message(club_id, topic_id):
    topic = ClubTopic.query.get_or_404(topic_id)

    # Verifica se é membro
    is_member = ClubMember.query.filter_by(
        club_id=club_id,
        user_id=current_user.id
    ).first() is not None

    if not is_member:
        abort(403)

    content = request.form.get('content', '').strip()
    if not content:
        flash('A mensagem não pode estar vazia', 'danger')
        return redirect(url_for('main.club_topic', club_id=club_id, topic_id=topic_id))

    message = ClubMessage(
        topic_id=topic.id,
        user_id=current_user.id,
        content=content
    )
    db.session.add(message)
    db.session.commit()

    return redirect(url_for('main.club_topic', club_id=club_id, topic_id=topic_id))


@main.route('/clubs/<int:club_id>/complete_topic/<int:topic_id>', methods=['GET', 'POST'])
@login_required
def complete_topic(club_id, topic_id):
    topic = ClubTopic.query.get_or_404(topic_id)
    club = topic.club

    if club.owner_id != current_user.id:
        abort(403)

    if request.method == 'POST':
        rating = int(request.form.get('rating', 5))
        comment = request.form.get('comment', f"Lido no clube '{club.name}'")

        existing_review = Review.query.filter_by(
            user_id=current_user.id,
            book_id=topic.book_id
        ).first()

        if existing_review:
            existing_review.rating = rating
            existing_review.comment = comment
        else:
            review = Review(
                user_id=current_user.id,
                book_id=topic.book_id,
                rating=rating,
                comment=comment,
                read=True
            )
            db.session.add(review)

        topic.end_date = datetime.utcnow()

        # Verificar se todos os tópicos foram concluídos
        incomplete_topics = ClubTopic.query.filter_by(
            club_id=club.id,
            end_date=None
        ).count()

        if incomplete_topics == 0:
            club.current_phase = 'completed'

        db.session.commit()
        flash(f'Discussão sobre "{topic.book.title}" concluída!', 'success')
        return redirect(url_for('main.club_detail', club_id=club_id))

    # Se for GET, mostrar formulário de avaliação
    book = topic.book
    existing_review = Review.query.filter_by(
        user_id=current_user.id,
        book_id=book.id
    ).first()

    return render_template('rate_club_book.html',
                           book=book,
                           review=existing_review,
                           club=club,  # Adicionei esta linha
                           topic=topic,  # Adicionei esta linha
                           club_id=club_id,
                           topic_id=topic_id)


@main.route('/invites')
@login_required
def view_invites():
    invites = current_user.get_pending_invites()
    return render_template('invites.html', invites=invites)


@main.route('/invites/<int:invite_id>/accept', methods=['POST'])
@login_required
def accept_invite(invite_id):
    invite = ClubInvite.query.get_or_404(invite_id)

    if invite.user_id != current_user.id:
        abort(403)

    # Verifica se há vagas
    club = Club.query.get(invite.club_id)
    current_members = ClubMember.query.filter_by(club_id=club.id).count()
    if current_members >= club.max_members:
        flash('O clube já atingiu o número máximo de membros', 'danger')
        return redirect(url_for('main.view_invites'))

    # Cria a associação
    member = ClubMember(
        club_id=club.id,
        user_id=current_user.id
    )
    db.session.add(member)

    # Atualiza o convite
    invite.status = 'accepted'
    db.session.commit()

    flash(f'Você entrou no clube {club.name}!', 'success')
    return redirect(url_for('main.club_detail', club_id=club.id))


@main.route('/invites/<int:invite_id>/reject', methods=['POST'])
@login_required
def reject_invite(invite_id):
    invite = ClubInvite.query.get_or_404(invite_id)

    if invite.user_id != current_user.id:
        abort(403)

    invite.status = 'rejected'
    db.session.commit()

    flash('Convite recusado', 'info')
    return redirect(url_for('main.view_invites'))


@main.route('/user/profile')
@login_required
def user_profile():
    return render_template('user_profile.html', user=current_user)


@main.route('/user/change_email', methods=['GET', 'POST'])
@login_required
def change_email():
    if request.method == 'POST':
        new_email = request.form.get('email')
        confirm_password = request.form.get('confirm_password')

        # Verificar senha atual
        if not current_user.verify_password(confirm_password):
            flash('Senha incorreta', 'danger')
            return redirect(url_for('main.change_email'))

        # Verificar se o email já existe
        if User.query.filter_by(email=new_email).first():
            flash('Este e-mail já está em uso', 'danger')
            return redirect(url_for('main.change_email'))

        current_user.email = new_email
        db.session.commit()
        flash('E-mail atualizado com sucesso!', 'success')
        return redirect(url_for('main.user_profile'))

    return render_template('change_email.html')


@main.route('/user/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')

        # Verificar senha atual
        if not current_user.verify_password(current_password):
            flash('Senha atual incorreta', 'danger')
            return redirect(url_for('main.change_password'))

        # Verificar se as novas senhas coincidem
        if new_password != confirm_password:
            flash('As senhas não coincidem', 'danger')
            return redirect(url_for('main.change_password'))

        if not is_password_strong(new_password):
            flash('A senha deve ter pelo menos 8 caracteres, incluindo maiúsculas, minúsculas e números', 'danger')
            return redirect(url_for('main.change_password'))

        # Atualizar senha
        current_user.password = generate_password_hash(new_password, method='pbkdf2:sha256')
        db.session.commit()
        flash('Senha alterada com sucesso!', 'success')
        return redirect(url_for('main.user_profile'))

    return render_template('change_password.html')


@main.route('/clubs/<int:club_id>/rate_book/<int:book_id>', methods=['GET', 'POST'])
@login_required
def rate_club_book(club_id, book_id):
    club = Club.query.get_or_404(club_id)
    book = Book.query.get_or_404(book_id)

    # Verificar se o usuário é membro do clube
    is_member = ClubMember.query.filter_by(
        club_id=club_id,
        user_id=current_user.id
    ).first() is not None

    if not is_member:
        abort(403)

    if request.method == 'POST':
        rating = int(request.form.get('rating', 5))
        comment = request.form.get('comment', f"Lido no clube '{club.name}'")

        existing_review = Review.query.filter_by(
            user_id=current_user.id,
            book_id=book_id
        ).first()

        if existing_review:
            existing_review.rating = rating
            existing_review.comment = comment
        else:
            review = Review(
                user_id=current_user.id,
                book_id=book_id,
                rating=rating,
                comment=comment,
                read=True
            )
            db.session.add(review)

        db.session.commit()
        flash('Avaliação salva com sucesso!', 'success')
        return redirect(url_for('main.club_detail', club_id=club_id))

    existing_review = Review.query.filter_by(
        user_id=current_user.id,
        book_id=book_id
    ).first()

    return render_template('rate_club_book.html',
                           book=book,
                           review=existing_review,
                           club_id=club_id)


@main.route('/clubs/<int:club_id>/restart', methods=['POST'])
@login_required
def restart_club(club_id):
    club = Club.query.get_or_404(club_id)

    if club.owner_id != current_user.id:
        abort(403)

    # Verificar se todos os tópicos foram concluídos
    incomplete_topics = ClubTopic.query.filter_by(
        club_id=club.id,
        end_date=None
    ).count()

    if incomplete_topics > 0:
        flash('Todos os livros devem ser concluídos antes de reiniciar', 'warning')
        return redirect(url_for('main.club_detail', club_id=club.id))

    # Reiniciar o clube
    club.current_phase = 'forming'
    club.current_cycle += 1

    # Limpar escolhas de livros dos membros
    ClubMember.query.filter_by(club_id=club.id).update({'book_id': None})

    db.session.commit()

    flash('Clube reiniciado com sucesso! Os membros podem escolher novos livros.', 'success')
    return redirect(url_for('main.club_detail', club_id=club.id))

