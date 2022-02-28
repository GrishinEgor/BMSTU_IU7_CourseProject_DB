DROP TABLE IF EXISTS author CASCADE;
DROP TABLE IF EXISTS book CASCADE;
DROP TABLE IF EXISTS reader CASCADE;
DROP TABLE IF EXISTS reading CASCADE;
DROP TABLE IF EXISTS user_data CASCADE;
DROP TYPE IF exists user_role_t;
DROP TYPE IF exists reading_status_t;
DROP FUNCTION IF EXISTS update_rating;
DROP FUNCTION IF EXISTS update_number_of_copies;
DROP FUNCTION IF EXISTS check_parts;
DROP TRIGGER IF EXISTS update_rating_trigger ON reading;
DROP TRIGGER IF EXISTS update_number_of_copies_trigger ON reading;
DROP TRIGGER IF EXISTS parts_connect_trigger ON book;
DROP ROLE IF EXISTS admin;
DROP ROLE IF EXISTS librarian;
DROP ROLE IF EXISTS reader;
DROP ROLE IF EXISTS guest;

--------------TABLES-----------------------------------------------------------
CREATE type user_role_t as enum (
	'admin',
	'librarian',
	'reader'
);

CREATE TABLE user_data (
    id SERIAL NOT NULL PRIMARY KEY,
	login TEXT NOT NULL UNIQUE, 
	password TEXT NOT NULL, 
	user_role user_role_t NOT NULL
);

CREATE TABLE IF NOT EXISTS author (
    id SERIAL NOT NULL PRIMARY KEY,
	name TEXT NOT NULL,
	surname TEXT NOT NULL,
	year_birth INT NOT NULL,
	year_death INT
);

CREATE TABLE IF NOT EXISTS book (
    id SERIAL NOT NULL PRIMARY KEY,
	id_author INT REFERENCES author(id) ON DELETE CASCADE NOT NULL,
	name TEXT UNIQUE NOT NULL,
	year_of_publication INT NOT NULL CHECK(year_of_publication > 1000),
	number_of_copies INT NOT NULL CHECK(number_of_copies >= 0),
	rating NUMERIC(3, 1) DEFAULT 0 CHECK(RATING >= 0 AND RATING <= 10) NOT NULL,
	id_last_part INT,
	id_next_part INT,
	path_to_cover TEXT
);

CREATE TABLE IF NOT EXISTS reader (
	id SERIAL NOT NULL PRIMARY KEY,
	login TEXT REFERENCES user_data(login) ON DELETE CASCADE NOT NULL,
	name TEXT NOT NULL,
	surname TEXT NOT NULL,
	birth_date DATE NOT NULL,
	email TEXT NOT NULL UNIQUE CHECK(email SIMILAR TO '%@%.%'),
	phone TEXT NOT NULL UNIQUE CHECK(phone SIMILAR TO '[0-9]{11}')
);

CREATE type reading_status_t as enum (
	'request_recieve',
	'in_reading',
	'request_return',
	'returned'
);

CREATE TABLE IF NOT EXISTS reading (
	id SERIAL NOT NULL PRIMARY key,
    id_book INT REFERENCES book(id) ON DELETE CASCADE NOT NULL,
	id_reader INT REFERENCES reader(id) ON DELETE CASCADE NOT NULL,
	date_request_recieve TIMESTAMP NOT NULL,
	date_recieved TIMESTAMP DEFAULT 'infinity' NOT NULL,
	date_request_return TIMESTAMP DEFAULT 'infinity' NOT NULL,
	date_returned TIMESTAMP DEFAULT 'infinity' NOT NULL,
	estimation REAL CHECK(estimation >= 0 and estimation <= 10),
	status reading_status_t NOT NULL
);

--------------TRIGGERS---------------------------------------------------------
CREATE FUNCTION update_rating() RETURNS TRIGGER AS 
$$
DECLARE
	new_rating REAL;
BEGIN
	new_rating = (
		SELECT COALESCE(AVG(estimation), 0)
		FROM reading 
		WHERE id_book = NEW.id_book AND estimation IS NOT NULL AND status = 'returned'
	);
	UPDATE book
	SET rating = new_rating
	WHERE id = NEW.id_book;
	RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_rating_trigger
AFTER UPDATE ON reading 
FOR EACH ROW 
WHEN (NEW.status = 'returned')
EXECUTE PROCEDURE update_rating();

CREATE FUNCTION update_number_of_copies() RETURNS TRIGGER AS 
$$
BEGIN
	IF NEW.status = 'in_reading' THEN
		UPDATE book
		SET number_of_copies = number_of_copies - 1
		WHERE id = NEW.id_book;
	ELSIF NEW.status = 'returned' THEN
		UPDATE book
		SET number_of_copies = number_of_copies + 1
		WHERE id = NEW.id_book;
	END IF;
	RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_number_of_copies_trigger
AFTER UPDATE ON reading 
FOR EACH ROW 
WHEN (NEW.status = 'in_reading' OR NEW.status = 'returned')
EXECUTE PROCEDURE update_number_of_copies();

CREATE FUNCTION check_parts() RETURNS TRIGGER AS
$$
DECLARE
	id_next_for_last INT;
	id_last_for_next INT;
BEGIN
	id_next_for_last = (SELECT id_next_part 
		FROM book
		WHERE id = NEW.id_last_part);
	id_last_for_next = (SELECT id_last_part 
		FROM book
		WHERE id = NEW.id_next_part);
	
	IF id_next_for_last IS NOT NULL OR id_last_for_next IS NOT NULL THEN 
		RETURN NULL;
	ELSE
		UPDATE book
		SET id_next_part = NEW.id
		WHERE id = NEW.id_last_part;
		UPDATE book
		SET id_last_part = NEW.id
		WHERE id = NEW.id_next_part;
		RETURN NEW;
	END IF;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER parts_connect_trigger
BEFORE INSERT ON book 
FOR EACH ROW EXECUTE PROCEDURE check_parts();


--------------ROLES------------------------------------------------------------
-- ROLE ADMIN
CREATE ROLE admin WITH SUPERUSER LOGIN PASSWORD '1234';

-- ROLE LIBRARIAN
CREATE ROLE librarian WITH LOGIN PASSWORD '1234';
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE book TO librarian;
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE reading TO librarian;
GRANT SELECT, INSERT, DELETE, UPDATE ON TABLE author TO librarian;
GRANT SELECT ON TABLE reader TO librarian;
GRANT SELECT ON TABLE user_data TO librarian;
GRANT USAGE, SELECT ON SEQUENCE reading_id_seq, book_id_seq, author_id_seq TO librarian;

-- ROLE READER
CREATE ROLE reader WITH LOGIN PASSWORD '1234';
GRANT SELECT ON TABLE book TO reader;
GRANT SELECT, INSERT, UPDATE ON TABLE reading TO reader;
GRANT SELECT ON TABLE author TO reader;
GRANT SELECT ON TABLE reader TO reader;
GRANT SELECT ON TABLE user_data TO reader;
GRANT USAGE, SELECT ON SEQUENCE reading_id_seq TO reader;
GRANT EXECUTE ON FUNCTION update_rating TO reader;

-- ROLE GUEST
CREATE ROLE guest WITH LOGIN PASSWORD '1234';
GRANT SELECT ON TABLE book TO guest;
GRANT SELECT ON TABLE author TO guest;
GRANT SELECT ON TABLE user_data TO guest;
--------------INSERT-----------------------------------------------------------

INSERT INTO author(name, surname, year_birth, year_death) VALUES
('Иван', 'Иванов', 1694, 1752),
('Пётр', 'Петров', 1204, 1235),
('Владимир', 'Сидоров', 1628, 1692),
('Анна', 'Желамская', 1941, 1986),
('Аделаида', 'Полякова', 1990, NULL),
('Светлана', 'Михеева', 1920, 1989),
('Родион', 'Зарубин', 1810, 1837),
('Евгения', 'Данильченко', 1690, 1754),
('Даниил', 'Сысоев', 1923, 1976),
('Ксения', 'Зарипова', 1982, NULL),
('Джоан', 'Роулинг', 1965, NULL);

INSERT INTO book(id_author, name, year_of_publication, number_of_copies, id_last_part, id_next_part, path_to_cover) VALUES
(11, 'Гарри Поттер и философский камень', 1997, 1000, NULL, NULL, 'book_cover/1.jpg'),
(11, 'Гарри Поттер и Тайная комната', 1998, 1000, 1, NULL, 'book_cover/2.jpg'),
(11, 'Гарри Поттер и узник Азкабана', 1999, 1000, 2, NULL, 'book_cover/3.jpg'),
(11, 'Гарри Поттер и Кубок трёх волшебников', 2000, 1000, 3, NULL, 'book_cover/4.jpg'),
(11, 'Гарри Поттер и Орден феникса', 2003, 1000, 4, NULL, 'book_cover/5.jpg'),
(11, 'Гарри Поттер и Принц-полукровка', 2005, 1000, 5, NULL, 'book_cover/6.jpg'),
(11, 'Гарри Поттер и Дары Смерти', 2007, 1000, 6, NULL, 'book_cover/7.jpg'),
(1, 'Прекрасный 17 век', 1720, 1, NULL, NULL, NULL),
(2, 'Ужасный 13 век', 1234, 2, NULL, NULL, NULL),
(3, 'Трепанация черепа в подробностях', 1678, 3, NULL, NULL, NULL),
(4, 'Яды и их классификация', 1976, 4, NULL, NULL, NULL),
(5, 'Как управлять Марсом', 2016, 5, NULL, NULL, NULL),
(6, 'Карманный справочник партизана', 1949, 6, NULL, NULL, NULL),
(7, 'Организация переворота с помощью табакерки', 1836, 1, NULL, NULL, NULL),
(8, 'Как побеждать шведов', 1725, 8, NULL, NULL, NULL);

INSERT INTO user_data(login, password, user_role) VALUES
('egor', '1234', 'reader'), -- 1234
('ann', '1234', 'reader'), -- 1234
('admin', '1234', 'admin'), -- 1234
('librarian', '1234', 'librarian'); -- 1234

INSERT INTO reader(login, name, surname, birth_date, email, phone) VALUES
('egor', 'Егор', 'Гришин', '2001-03-29', 'grischin.egor2001@yandex.ru', '79687961168'),
('ann', 'Анна', 'Шишихина', '2000-01-01', 'super.ann001@mail.ru', '77777777777');