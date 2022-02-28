from flask import Flask
from flask import render_template
from flask import redirect
from flask import url_for
from flask import request
from flask import flash
from datetime import datetime
import psycopg2
from psycopg2.extras import DictCursor

app = Flask(__name__)
app.config['SECRET_KEY'] = 'library'
dbname = 'CP_DB_library'
password_dict = {'admin': '1234',
                 'librarian': '1234',
                 'reader': '1234',
                 'guest': '1234'}
user_role = 'guest'
user_login = None
user_id_reader = None
conn = psycopg2.connect(dbname=dbname, user=user_role, password=password_dict[user_role], host='localhost')
cursor = conn.cursor(cursor_factory=DictCursor)


@app.route('/', methods=['GET'])
def main():
    return render_template('main.html', user_role=user_role)


@app.route('/all_books/', methods=['GET'])
def all_books():
    cursor.execute('''SELECT author.name as name_author, author.surname as surname_author, book.*
                      FROM author JOIN book ON author.id = book.id_author
                      ORDER BY id;''')
    books = cursor.fetchall()
    return render_template('all_books.html', user_role=user_role, books=books)


@app.route('/contacts/', methods=['GET'])
def contacts():
    return render_template('contacts.html', user_role=user_role)


@app.route('/book/<id_book>/', methods=['GET'])
@app.route('/book/<id_book>/<action>', methods=['GET'])
@app.route('/book/<id_book>/<action>?<estimation>', methods=['GET'])
def book_id(id_book, action=None, estimation=None):
    cursor.execute('''SELECT author.name as name_author, author.surname as surname_author, book.*
                      FROM author JOIN book ON author.id = book.id_author
                      WHERE book.id = %s''', (id_book, ))
    book = cursor.fetchone()
    cursor.execute('''
                            WITH RECURSIVE last_parts AS (
                                SELECT *
                                FROM book
                                WHERE id = %s
                                UNION ALL
                                SELECT book.*
                                FROM last_parts JOIN book ON last_parts.id_last_part = book.id
                            ), next_parts AS (
                                SELECT *
                                FROM book
                                WHERE id = %s
                                UNION ALL
                                SELECT book.*
                                FROM next_parts JOIN book ON next_parts.id_next_part = book.id
                            ), res AS (
                                SELECT * FROM last_parts
                                UNION
                                SELECT * FROM next_parts
                            )
                            SELECT * 
                            FROM res 
                            WHERE id != %s
                            ORDER BY id_next_part;''', (id_book, id_book, id_book))
    book_series = cursor.fetchall()
    status = 'returned'
    if user_role == 'reader':
        cursor.execute('''SELECT status 
                          FROM reading 
                          WHERE id_book = %s AND id_reader = %s
                          ORDER BY date_request_recieve DESC''', (id_book, user_id_reader))
        res = cursor.fetchone()
        if res:
            status = res['status']

    if action == 'request_recieve':
        cursor.execute("""INSERT INTO reading(id_book, id_reader, date_request_recieve, status) VALUES
                          (%s, %s, %s, 'request_recieve')""", (id_book, user_id_reader, datetime.now()))
        conn.commit()
        status = 'request_recieve'
    elif action == 'request_return':
        cursor.execute("""UPDATE reading
                          SET status = 'request_return', date_request_return = %s, estimation = %s
                          WHERE id_book = %s AND id_reader = %s AND status = 'in_reading'""",
                          (datetime.now(), estimation, id_book, user_id_reader))
        conn.commit()
        status = 'request_return'

    return render_template('book.html', user_role=user_role, book=book, status=status, book_series=book_series)


@app.route('/login_user/', methods=['GET', 'POST'])
def login_user():
    global conn, cursor, user_role, user_login, user_id_reader
    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        cursor.execute("""SELECT *
                          FROM user_data
                          WHERE login = %s AND password = %s;""", (login, password))
        res = cursor.fetchone()
        if res:
            conn.close()
            user_role = res['user_role']
            user_login = login
            conn = psycopg2.connect(dbname=dbname, user=user_role, password=password_dict[user_role], host='localhost')
            cursor = conn.cursor(cursor_factory=DictCursor)
            if user_role == 'reader':
                cursor.execute("SELECT id FROM reader WHERE login = %s", (login, ))
                user_id_reader = cursor.fetchone()['id']
            return redirect(url_for('user_space'))
        else:
            flash('Неправильный логин или пароль!')

    return render_template('login_user.html', user_role=user_role)


@app.route('/quit', methods=['GET'])
def quit():
    global conn, cursor, user_role, user_login, user_id_reader
    conn.close()
    user_role = 'guest'
    user_login = None
    user_id_reader = None
    conn = psycopg2.connect(dbname=dbname, user=user_role, password=password_dict[user_role], host='localhost')
    cursor = conn.cursor(cursor_factory=DictCursor)
    return redirect(url_for('main'))


@app.route('/user_space', methods=['GET'])
def user_space():
    return render_template('user_space.html', user_role=user_role)


@app.route('/add_user/<role>', methods=['GET', 'POST'])
@app.route('/add_user?<role>', methods=['GET', 'POST'])
def add_user(role):
    if request.method == 'POST':
        login = request.form.get('login')
        password = request.form.get('password')
        try:
            cursor.execute("""INSERT INTO user_data(login, password, user_role) VALUES
                              (%s, %s, %s);""", (login, password, role))
            if role == 'reader':
                name = request.form.get('name')
                surname = request.form.get('surname')
                birth_date = request.form.get('birth_date')
                email = request.form.get('email')
                phone = request.form.get('phone')
                cursor.execute("""INSERT INTO reader(login, name, surname, birth_date, email, phone) VALUES
                                (%s, %s, %s, %s, %s, %s);""", (login, name, surname, birth_date, email, phone))
            flash('Пользователь успешно добавлен')
        except Exception:
            flash('Неправильный формат введённых данных!')
        finally:
            conn.commit()

    return render_template('add_user.html', user_role=user_role, role=role)


@app.route('/delete_user', methods=['GET', 'POST'])
def delete_user():
    if request.method == 'POST':
        login = request.form.get('login')
        if login != user_login:
            cursor.execute("SELECT * FROM user_data WHERE login = %s", (login, ))
            if cursor.fetchone():
                cursor.execute("DELETE FROM user_data WHERE login = %s", (login, ))
                conn.commit()
                flash('Пользователь успешно удалён')
            else:
                flash('Нет пользователя с таким логином!')
        else:
            flash('Нельзя удалить себя!')
    return render_template('delete_user.html', user_role=user_role)


@app.route('/all_readings/<status>', methods=['GET'])
def all_readings(status):
    readings = []
    if user_role == 'librarian':
        cursor.execute("""SELECT reading.*, book.id AS book_id, book.name AS book_name, book.number_of_copies, 
                          reader.name AS reader_name, reader.surname AS reader_surname
                      FROM reader JOIN (reading JOIN book ON reading.id_book = book.id) ON reader.id = reading.id_reader
                      WHERE reading.status = %s""", (status, ))
        readings = cursor.fetchall()
    elif user_role == 'reader':
        cursor.execute("""SELECT reading.*, book.id AS book_id, book.name AS book_name, book.number_of_copies, 
                                  reader.name AS reader_name, reader.surname AS reader_surname
                              FROM reader JOIN (reading JOIN book ON reading.id_book = book.id) ON reader.id = reading.id_reader
                              WHERE reading.status = %s AND reader.id = %s""", (status, user_id_reader))
        readings = cursor.fetchall()
    return render_template('all_readings.html', user_role=user_role, readings=readings, status=status)


@app.route('/approve_request/<id_request>/<status>', methods=['GET'])
def approve_request(id_request, status):
    if status == 'request_recieve':
        cursor.execute("""UPDATE reading
                          SET status = 'in_reading', date_recieved = %s
                          WHERE id = %s""", (datetime.now(), id_request))
    elif status == 'request_return':
        cursor.execute("""UPDATE reading
                                  SET status = 'returned', date_recieved = %s
                                  WHERE id = %s""", (datetime.now(), id_request))
    conn.commit()
    return redirect(url_for('all_readings', status=status))


@app.route('/add_author/', methods=['GET', 'POST'])
def add_author():
    if request.method == 'POST':
        name = request.form.get('name')
        surname = request.form.get('surname')
        year_birth = request.form.get('year_birth')
        year_death = request.form.get('year_death')
        try:
            cursor.execute("""INSERT INTO author(name, surname, year_birth, year_death) VALUES
                            (%s, %s, %s, %s);""", (name, surname, year_birth, year_death))
            flash('Автор успешно добавлен')
        except:
            flash('Неправильный формат введённых данных!')
        finally:
            conn.commit()

    return render_template('add_author.html', user_role=user_role)


@app.route('/all_authors/', methods=['GET'])
def all_authors():
    cursor.execute("""SELECT author.*, COUNT(author.id) AS count_books
                      FROM author LEFT JOIN book ON author.id = book.id_author
                      GROUP BY author.id
                      ORDER BY author.id;""")
    authors = cursor.fetchall()
    return render_template('all_authors.html', user_role=user_role, authors=authors)


@app.route('/author/<id_author>', methods=['GET'])
def author(id_author):
    cursor.execute("""SELECT author.*, COUNT(author.id) AS count_books
                      FROM author LEFT JOIN book ON author.id = book.id_author
                      WHERE author.id = %s
                      GROUP BY author.id;""", (id_author, ))
    author_data = cursor.fetchone()
    cursor.execute("""SELECT book.*
                      FROM author JOIN book ON author.id = book.id_author
                      WHERE author.id = %s""", (id_author, ))
    books = cursor.fetchall()
    return render_template('author.html', user_role=user_role, author=author_data, books=books)


@app.route('/add_book/<id_author>', methods=['POST'])
def add_book(id_author):
    name = request.form.get('name')
    year_of_publication = request.form.get('year_of_publication')
    number_of_copies = request.form.get('number_of_copies')
    name_last_part = request.form.get('name_last_part')
    name_next_part = request.form.get('name_next_part')
    id_last_part = None
    id_next_part = None
    if name_last_part:
        cursor.execute("SELECT * FROM book WHERE name = %s AND id_author = %s", (name_last_part, id_author))
        last_part = cursor.fetchone()
        if last_part:
            id_last_part = last_part['id']
        else:
            flash('Несуществующее название предыдущей части')
            return redirect(url_for('author', id_author=id_author))
    if name_next_part:
        cursor.execute("SELECT * FROM book WHERE name = %s AND id_author = %s", (name_next_part, id_author))
        next_part = cursor.fetchone()
        if not next_part:
            id_next_part = next_part['id']
        else:
            flash('Несуществующее название следующей части')
            return redirect(url_for('author', id_author=id_author))
    cover = request.files['cover']
    if cover:
        full_path_to_cover = './static/book_cover/{}.{}'.format(name, cover.filename.rsplit('.', 1)[1])
        path_to_cover = 'book_cover/{}.{}'.format(name, cover.filename.rsplit('.', 1)[1])
        cover.save(full_path_to_cover)
    try:
        cursor.execute("""INSERT INTO book(id_author, name, year_of_publication, number_of_copies, id_last_part, id_next_part, path_to_cover) VALUES
                          (%s, %s, %s, %s, %s, %s, %s)""", (id_author, name, year_of_publication, number_of_copies, id_last_part, id_next_part, path_to_cover))
        flash('Книга успешно добавлена')
    except:
        flash('Неправильный формат введённых данных!')
    finally:
        conn.commit()
    return redirect(url_for('author', id_author=id_author))