import logging
import sqlite3
import functions
import time


from telebot import TeleBot
from telebot import types

# constants
PREFERRED_LANGUAGE = 'UA'
DB_NAME = 'planner_bot_DB.sqlite'

bot = TeleBot('')

# setting up a logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s:%(name)s:%(funcName)s:%(message)s')

file_handler = logging.FileHandler('planner_log.log')
file_handler.setFormatter(formatter)

logger.addHandler(file_handler)

logger.info('Starting')

# getting a text for messages with PREFERRED_LANGUAGE
common_phrases = functions.get_dialog_profile(PREFERRED_LANGUAGE)

# making a connection and creating tables
connection = sqlite3.connect(DB_NAME)
cursor = connection.cursor()

# status - 0 - in process, 1 - completed, 2 - incompleted before deadline
# importance - 0 - grey, 1 - green, 2 - yellow, 3 - red
cursor.executescript(
    '''
CREATE TABLE IF NOT EXISTS Users(
id INTEGER NOT NULL PRIMARY KEY  AUTOINCREMENT UNIQUE,
tele_id INTEGER NOT NULL UNIQUE,
language TEXT,
last_callback TEXT,
buffer TEXT
);

CREATE TABLE IF NOT EXISTS Sheets(
id INTEGER NOT NULL PRIMARY KEY  AUTOINCREMENT UNIQUE,
time FLOAT,
user_id INTEGER NOT NULL,
name TEXT,
UNIQUE (user_id, name)
);

CREATE TABLE IF NOT EXISTS Tasks(
id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT UNIQUE,
task TEXT,
deadline FLOAT,
status INTEGER,
importance INTEGER,
user_id INTEGER,
sheet_id INTEGER NOT NULL,
UNIQUE(task, sheet_id)
)
'''
)

connection.commit()

cursor.close()
connection.close()


# returns a main menu keyboard markup
def main_menu_markup(language):

    buttons_text = functions.get_dialog_profile(language)['main menu']
    markup = types.ReplyKeyboardMarkup()

    for text in buttons_text:
        markup.add(types.KeyboardButton(text))

    return markup


@bot.message_handler(func=lambda x: x.text == 'SWITCH THE LANGUAGE' or x.text == 'СМЕНИТЬ ЯЗЫК' or x.text == 'ЗМІНИТИ МОВУ')
def change_language(message):
    if message.chat.type == 'private':
        logger.info(f'User with id - {message.from_user.id} is trying to switch the language.')

        # making a keyboard with language options
        btn1 = types.KeyboardButton('🇺🇦')
        btn2 = types.KeyboardButton('🇬🇧')
        btn3 = types.KeyboardButton('🇷🇺')

        markup = types.ReplyKeyboardMarkup()
        markup.add(btn1, btn2, btn3)

        db_connection = sqlite3.connect(DB_NAME)
        db_cursor = db_connection.cursor()

        # sending a keyboard
        msg = bot.send_message(message.from_user.id,
                               functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                   'lang switch'][1], reply_markup=markup)

        db_cursor.close()
        db_connection.close()

        # changing the language when user makes an input
        bot.register_next_step_handler(msg, set_language)


def set_language(message):
    logger.info('Trying to switch the language.')

    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()

    # determine the new language
    if message.text == '🇺🇦':
        new_language = 'UA'
    elif message.text == '🇷🇺':
        new_language = 'RU'
    elif message.text == '🇬🇧':
        new_language = 'EN'

    try:
        # updating a language
        db_cursor.execute('UPDATE Users SET language = ? WHERE tele_id = ?', (new_language, message.from_user.id))
        db_connection.commit()
        bot.send_message(message.from_user.id,
                         functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                             'lang switch'][2],
                         reply_markup=main_menu_markup(new_language))
        logger.info(f'Switched successfully to {new_language}')
    except UnboundLocalError:
        # user sent invalid input
        bot.send_message(message.from_user.id,
                         functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                             'lang switch'][3],
                         reply_markup=main_menu_markup(functions.get_language(db_cursor, message.from_user.id)))
        logger.info('UnboundLocalError.')

    db_cursor.close()
    db_connection.close()


@bot.message_handler(commands=['start'])
def starter(message):
    # the bot does not work in group chats
    if message.chat.type == 'group' or message.chat.type == 'supergroup':
        bot.send_message(message.chat.id, common_phrases['group'], reply_to_message_id=message.message_id)

    # private chat
    elif message.chat.type == 'private':

        logger.info(f'User with id - {message.from_user.id} is trying to register.')

        db_connection = sqlite3.connect(DB_NAME)
        db_cursor = db_connection.cursor()

        # checking if user is already registered
        logger.info('Checking if user is already registered')

        db_cursor.execute('SELECT id FROM Users WHERE tele_id = ?', (message.from_user.id,))
        registered = db_cursor.fetchone()

        # registration in the database
        if not registered:

            logger.info('User is not registered. Performing a registration...')
            db_cursor.execute('INSERT INTO Users(tele_id, language) VALUES(?, ?)',
                              (message.from_user.id, PREFERRED_LANGUAGE))

            # creating a language markup
            markup = types.InlineKeyboardMarkup()

            btn_ua = types.InlineKeyboardButton(text='🇺🇦', callback_data='setlang UA')
            btn_ru = types.InlineKeyboardButton(text='🇷🇺', callback_data='setlang RU')
            btn_en = types.InlineKeyboardButton(text='🇬🇧', callback_data='setlang EN')

            markup.add(btn_ua, btn_ru, btn_en)
            bot.send_message(message.from_user.id,
                             functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                 'language hint'], reply_markup=markup)

            db_connection.commit()
            logger.info('Success')
        else:

            logger.info('User has already been registered.')
            bot.send_message(message.from_user.id,
                             functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                 'already started'],
                             reply_markup=main_menu_markup(PREFERRED_LANGUAGE))


@bot.message_handler(func=lambda
        x: x.text == 'CREATE NEW TODO LIST' or x.text == 'СОЗДАТЬ НОВЫЙ TODO СПИСОК' or x.text == 'СТВОРИТИ TODO СПИСОК')
def create_list(message):  # creates a new list
    if message.chat.type == 'private':
        logger.info(f'User with id - {message.from_user.id} is trying to create new list.')

        db_connection = sqlite3.connect(DB_NAME)
        db_cursor = db_connection.cursor()

        msg = bot.send_message(message.from_user.id,
                               functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                   'todo creation'][2])

        logger.info('Calling next step handler.')
        bot.register_next_step_handler(msg, create_list_next_step)


def create_list_next_step(message):
    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()

    # checking if name is not to long
    if len(message.text) > 1000 or message.text.find('_') != -1:
        msg = bot.send_message(message.from_user.id,
                         functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                             'todo creation'][1])
        bot.register_next_step_handler(msg, create_list_next_step)
        logger.info('The name is too long.')
    else:

        # getting a current time
        cur_time = time.time()

        # getting a user_id in DB
        db_cursor.execute('SELECT id FROM Users WHERE tele_id = ?', (message.from_user.id,))

        fetched = True
        try:
            db_user_id = db_cursor.fetchone()[0]
            logger.info('User is registered. Proceeding...')
        except TypeError:
            bot.send_message(message.from_user.id,
                             functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                 'lang switch'][3])
            fetched = False
            logger.info('User is not registered. Operation is unsuccessful.')

        # if user is registered
        if fetched:

            # trying to insert new list to the DB
            try:
                db_cursor.execute('INSERT INTO Sheets(time, user_id, name) VALUES(? , ?, ?)',
                                  (cur_time, db_user_id, message.text))

                markup = types.InlineKeyboardMarkup()

                lists = functions.get_lists_db(db_cursor, message.from_user.id)

                # making a keyboard to show the list
                i = 0
                while i < len(lists):
                    if lists[i][2] == message.text:
                        break
                    i += 1

                markup.add(types.InlineKeyboardButton(text=functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['todo creation'][-1],
                                                      callback_data=f'getlist {message.text.replace(" ", "_")} {i}'
                                                      ))
                bot.send_message(message.from_user.id,
                                 functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                     'todo creation'][0], reply_markup=markup)
                logger.info('Created.')

            # if name is not unique
            except sqlite3.IntegrityError:
                bot.send_message(message.from_user.id,
                                 functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                     'todo creation'][3])

                logger.info('Name of the list is not unique. Operation is unsuccessful.')

    db_connection.commit()

    db_cursor.close()
    db_connection.close()


@bot.message_handler(func=lambda x: x.text == 'МОЇ СПИСКИ' or x.text == 'MY LISTS' or x.text == 'МОИ СПИСКИ')
def get_lists(message):
    if message.chat.type == 'private':
        db_connection = sqlite3.connect(DB_NAME)
        db_cursor = db_connection.cursor()

        logger.info(f'User with id - {message.from_user.id} is trying to get list of lists. Fetching data from DB...')

        # getting a data from a db (format - [(id1, time1, name1),...,(idn, timen, namen), ])
        lists = functions.get_lists_db(db_cursor, message.from_user.id)

        # user has no lists
        if not len(lists):
            bot.send_message(message.from_user.id,
                             functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                 'get lists'][0])
            logger.info('User has no lists.')
        else:
            i = 0
            phrases = functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['get lists'][
                1]

            # setting a keyboard
            markup = types.InlineKeyboardMarkup()
            markup.row_width = 4

            while i < len(lists):
                markup.add(types.InlineKeyboardButton(lists[i][2], callback_data=f'getlist {lists[i][2].replace(" ", "_")} {i}'))
                i += 1

            bot.send_message(message.from_user.id, phrases, reply_markup=markup)

            logger.info('Success.')

        db_cursor.close()
        db_connection.close()


@bot.callback_query_handler(func=lambda call: True)
def universal_callback_handler(call):
    call_list = call.data.split()

    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()

    # saving a callback to access it in the future
    db_cursor.execute('UPDATE Users SET last_callback = ? WHERE tele_id = ?', (call.data, call.from_user.id))
    db_connection.commit()
    # handling a call from 'choose list' keyboard
    if call_list[0] == 'getlist':
        call_list[1] = call_list[1].replace("_", " ")
        logger.info(
            f'User with id - {call.from_user.id} is trying to get a list {call_list[1]}. Fetching data from DB...')

        # getting the lists
        lists = functions.get_lists_db(db_cursor, call.from_user.id)

        # checking if data is correct
        found = False
        try:
            if call_list[1] == lists[int(call_list[2])][2]:
                found = True
        except IndexError:
            pass

        if found:
            logger.info('Data is correct.')

            # getting tasks from the list
            db_cursor.execute('SELECT task, deadline, status, importance FROM Tasks WHERE sheet_id = ? ORDER BY status',
                              (int(lists[int(call_list[2])][0]),))
            tasks = db_cursor.fetchall()

            # there`s no tasks in the list
            if not len(tasks):
                answer = '*' + call_list[1] + '*' + ':\n\n' + '🔹' * 15 + '\n\n_' + \
                         functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['get lists'][
                             2] + '_\n\n' + '🔹' * 15

                # making a button that allows to add a task
                markup = types.InlineKeyboardMarkup()
                markup.add(types.InlineKeyboardButton(
                    text=functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['add task'][
                        0],
                    callback_data=f'addtask  {call_list[1].replace(" ", "_")}'))

                bot.edit_message_text(answer, message_id=call.message.message_id, chat_id=call.from_user.id,
                                      parse_mode='Markdown', reply_markup=markup)
                bot.answer_callback_query(call.id)

            # displaying list
            else:
                result = ''
                for task in tasks:
                    result += functions.task_parser(task) + '\n\n'

                answer = '*' + call_list[1] + '*' + ':\n\n' + '🔹' * 15 + '\n\n' + result + '🔹' * 15

                markup = types.InlineKeyboardMarkup()

                btn1 = types.InlineKeyboardButton(
                    text=functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['add task'][0],
                    callback_data=f'addtask  {call_list[1].replace(" ", "_")}')
                btn2 = types.InlineKeyboardButton(
                    text=functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['buttons'][0],
                    callback_data=f'markdone {call_list[1].replace(" ", "_")}'
                )

                btn3 = types.InlineKeyboardButton(
                    text=functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['buttons'][1],
                    callback_data=f'resetdeadline {call_list[1].replace(" ", "_")}'
                )

                btn4 = types.InlineKeyboardButton(
                    text=functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['buttons'][2],
                    callback_data=f'deletetask {call_list[1].replace(" ", "_")}'
                )
                markup.row_width = 2
                markup.add(btn1, btn4)
                markup.add(btn2)
                markup.add(btn3)

                bot.edit_message_text(answer, message_id=call.message.message_id, chat_id=call.from_user.id,
                                      parse_mode='Markdown', reply_markup=markup)

        # list is not found
        else:
            bot.send_message(call.from_user.id,
                             functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)[
                                 'lang switch'][3])

            logger.info(f'Unable to find list {call_list[1]} in the database...')
            bot.answer_callback_query(call.id)

    # handling a call from add task button
    elif call_list[0] == 'addtask':
        logger.info(f'User with id - {call.from_user.id} is trying to add a task  to a list {call_list[1]}.')

        exists = functions.list_existence(call_list[1].replace('_', ' '), db_cursor, call.from_user.id)

        if exists:
            msg = bot.send_message(call.from_user.id,
                                   functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['add task'][1])

            bot.answer_callback_query(call.id)
            bot.register_next_step_handler(msg, name_step)
        else:
            bot.answer_callback_query(call.id, text=
            functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['list not exist'])

    # handling a call from mark as done button
    elif call_list[0] == 'markdone':

        exists = functions.list_existence(call_list[1].replace("_", " "), db_cursor, call.from_user.id)
        if exists:
            markup = functions.tasks_buttons(db_cursor, call_list[1], call.from_user.id, 'donetask')
            bot.edit_message_text(functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['markdone'][0],
                                  message_id=call.message.message_id, chat_id=call.from_user.id, reply_markup=markup)

            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, text=
            functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['list not exist'])

    # handling a call from delete task button
    elif call_list[0] == 'deletetask':

        exists = functions.list_existence(call_list[1].replace("_", " "), db_cursor, call.from_user.id)

        if exists:
            markup = functions.tasks_buttons(db_cursor, call_list[1], call.from_user.id, 'deltask')
            bot.edit_message_text(functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['markdone'][0],
                                  message_id=call.message.message_id, chat_id=call.from_user.id, reply_markup=markup)

            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, text=
            functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['list not exist'])

    # handling a call from set deadline task
    elif call_list[0] == 'resetdeadline':

        exists = functions.list_existence(call_list[1].replace("_", " "), db_cursor, call.from_user.id)

        if exists:
            markup = functions.tasks_buttons(db_cursor, call_list[1], call.from_user.id, 'setdeadline')
            bot.edit_message_text(
                functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['markdone'][0],
                message_id=call.message.message_id, chat_id=call.from_user.id, reply_markup=markup)

            bot.answer_callback_query(call.id)
        else:
            bot.answer_callback_query(call.id, text=
            functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['list not exist'])

    # handling a call from button with task name
    elif call_list[0] == 'donetask':
        db_cursor.execute('UPDATE Tasks SET status = ? WHERE sheet_id = ? AND id = ?', (1, int(call_list[2]), int(call_list[1])))
        db_connection.commit()

        db_cursor.execute('SELECT name FROM Sheets WHERE id = ?', (int(call_list[2]),))
        sheet_name = db_cursor.fetchone()[0]
        lists = functions.get_lists_db(db_cursor, call.from_user.id)

        # making a keyboard to show the lists
        i = 0
        while i < len(lists):
            if lists[i][2] == sheet_name:
                break
            i += 1

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text=functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['add task'][10],
                                              callback_data=f'getlist {sheet_name.replace(" ", "_")} {i}'))

        bot.edit_message_text(functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['markdone'][2],
                              message_id=call.message.message_id, chat_id=call.from_user.id, reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call_list[0] == 'deltask':
        db_cursor.execute('DELETE FROM Tasks WHERE sheet_id = ? AND id = ?', (int(call_list[2]), int(call_list[1])))
        db_connection.commit()

        db_cursor.execute('SELECT name FROM Sheets WHERE id = ?', (int(call_list[2]),))
        sheet_name = db_cursor.fetchone()[0]
        lists = functions.get_lists_db(db_cursor, call.from_user.id)

        # making a keyboard to show the lists
        i = 0
        while i < len(lists):
            if lists[i][2] == sheet_name:
                break
            i += 1

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text=functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['add task'][10],
                                              callback_data=f'getlist {sheet_name.replace(" ", "_")} {i}'))

        bot.edit_message_text(functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['markdone'][3],
                              message_id=call.message.message_id, chat_id=call.from_user.id, reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif call_list[0] == 'setdeadline':

        msg = bot.send_message(call.from_user.id,
                               functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)[
                                   'add task'][5],
                               parse_mode='Markdown')
        bot.answer_callback_query(call.id)
        bot.register_next_step_handler(msg, deadline_change)

    elif call_list[0] == 'deletelist':

        logger.info(f'Deleting a list with id - {call_list[1]}')

        db_cursor.execute('DELETE FROM Tasks WHERE sheet_id = ?', (int(call_list[1]),))
        db_cursor.execute('DELETE FROM Sheets WHERE id = ?', (int(call_list[1]),))

        db_connection.commit()

        bot.edit_message_text(functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['delete list'][1],
                              message_id=call.message.message_id, chat_id=call.from_user.id)

        bot.answer_callback_query(call.id)

    # changing the language
    elif call_list[0] == 'setlang':

        db_cursor.execute('UPDATE Users SET language = ? WHERE tele_id = ?', (call_list[1], call.from_user.id))
        db_connection.commit()

        try:
            bot.edit_message_text(functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['lang switch'][2],
                                  chat_id=call.from_user.id,
                                  message_id=call.message.message_id)

            bot.answer_callback_query(call.id)

            bot.send_message(call.from_user.id, functions.get_lang_profile_chat(db_cursor, call.from_user.id, PREFERRED_LANGUAGE)['started'],
                             reply_markup=main_menu_markup(functions.get_language(db_cursor, call.from_user.id)))
        except TypeError:
            db_cursor.execute('UPDATE Users SET language = ? WHERE tele_id = ?', (PREFERRED_LANGUAGE, call.from_user.id))
            bot.answer_callback_query(call.id, text='Something strange has happened.')

    db_cursor.close()
    db_connection.close()


def deadline_change(message):

    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()

    correct = functions.get_timestamp(message.text)

    # deadline data is incorrect
    if not correct:
        msg = bot.send_message(message.from_user.id,
                               functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                   'add task'][4])
        logger.info('Problems with date.Trying again...')
        bot.register_next_step_handler(msg, deadline_change)

    else:

        callback = functions.last_callback(db_cursor, message.from_user.id).split()
        if callback[0] == 'setdeadline':
            db_cursor.execute('UPDATE Tasks SET deadline = ? WHERE sheet_id = ? AND id = ?',
                              (correct, int(callback[2]), int(callback[1])))

            # making a button to open the list
            lists = functions.get_lists_db(db_cursor, message.from_user.id)

            db_cursor.execute('SELECT name FROM Sheets WHERE id = ?', (int(callback[2]),))
            sheet_name = db_cursor.fetchone()[0]

            i = 0
            while i < len(lists):
                if lists[i][2] == sheet_name:
                    break
                i += 1

            phrases = functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['add task']

            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton(text=phrases[10], callback_data=f'getlist {sheet_name.replace(" ", "_")} {i}'))

            bot.send_message(message.from_user.id, phrases[11], reply_markup=markup)

            db_connection.commit()
            db_cursor.close()
            db_connection.close()


# next_step_handlers for adding tasks:
def name_step(message):
    logger.info('Processing name step...')

    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()

    # checking if data is correct
    if len(message.text) > 1000:
        msg = bot.send_message(message.from_user.id,
                         functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                             'add task'][2])
        logger.info('Task name is too long.Or "_"-rule is violated')

        bot.register_next_step_handler(msg, name_step)

    else:
        # getting a last callback
        callback = functions.last_callback(db_cursor, message.from_user.id).split()

        if callback[0] == 'addtask':

            logger.info('Getting a sheet_id from db...')

            sheet_id = functions.get_sheet_id(db_cursor, message.from_user.id, callback[1].replace("_", " "))
            try:
                db_cursor.execute('INSERT INTO Tasks(task, sheet_id, status) VALUES(?, ?, ?)', (message.text, sheet_id, 0))
                db_cursor.execute('UPDATE Users SET buffer = ? WHERE tele_id = ?', (message.text, message.from_user.id))
                logger.info('Tasks name was inserted successfully.')

                msg = bot.send_message(message.from_user.id,
                                       functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['add task'][5],
                                       parse_mode='Markdown')

                bot.register_next_step_handler(msg, deadline_step)
            except sqlite3.IntegrityError:
                msg = bot.send_message(message.from_user.id, functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                             'add task'][3])

                logger.info('Name is not unique.Trying again.')
                bot.register_next_step_handler(msg, name_step)

    db_connection.commit()

    db_cursor.close()
    db_connection.close()


def deadline_step(message):
    logger.info('Processing deadline step...')
    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()

    correct = functions.get_timestamp(message.text)

    # deadline data is incorrect
    if not correct:
        msg = bot.send_message(message.from_user.id, functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['add task'][4])
        logger.info('Problems with date.Trying again...')
        bot.register_next_step_handler(msg, deadline_step)

    # deadline data is correct
    else:
        # getting last callback
        callback = functions.last_callback(db_cursor, message.from_user.id).split()
        if callback[0] == 'addtask':
            sheet_id = functions.get_sheet_id(db_cursor, message.from_user.id, callback[1].replace("_", " "))

            # saving data
            db_cursor.execute('SELECT buffer FROM Users WHERE tele_id = ?', (message.from_user.id,))

            db_cursor.execute('UPDATE Tasks SET deadline = ? WHERE task = ? AND sheet_id = ?', (correct, db_cursor.fetchone()[0], sheet_id))

            logger.info('Deadline was successfully set. Processing priority step...')

            # setting up a priority keyboard
            markup = types.ReplyKeyboardMarkup()
            markup.row_width = 2
            markup.add(types.KeyboardButton('⬜'), types.KeyboardButton('🟩'), types.KeyboardButton('🟨'), types.KeyboardButton('🟥'))

            msg = bot.send_message(message.from_user.id,
                                   functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['add task'][6],
                                   reply_markup=markup)

            bot.register_next_step_handler(msg, priority_step)

    db_connection.commit()

    db_cursor.close()
    db_connection.close()


def priority_step(message):

    importance = -1

    if message.text == '⬜':
        importance = 0
    elif message.text == '🟩':
        importance = 1
    elif message.text == '🟨':
        importance = 2
    elif message.text == '🟥':
        importance = 3

    db_connection = sqlite3.connect(DB_NAME)
    db_cursor = db_connection.cursor()

    # checking if data is correct
    if importance != -1:

        callback = functions.last_callback(db_cursor, message.from_user.id).split()
        sheet_id = functions.get_sheet_id(db_cursor, message.from_user.id, callback[1].replace("_", " "))

        # saving data
        db_cursor.execute('SELECT buffer FROM Users WHERE tele_id = ?', (message.from_user.id,))

        db_cursor.execute('UPDATE Tasks SET importance = ? WHERE task = ? AND sheet_id = ?',
                          (importance, db_cursor.fetchone()[0], sheet_id))

        logger.info('Priority was successfully set.')
        # sending main menu keyboard
        markup = main_menu_markup(functions.get_language(db_cursor, message.from_user.id))
        bot.send_message(message.from_user.id,
                         functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                             'add task'][7],
                         reply_markup=markup)

        # making a button to open the list
        lists = functions.get_lists_db(db_cursor, message.from_user.id)

        i = 0
        while i < len(lists):
            if lists[i][2] == callback[1].replace("_", " "):
                break
            i += 1

        phrases = functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['add task']

        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton(text=phrases[10], callback_data=f'getlist {callback[1].replace(" ", "_")} {i}'))

        # sending a button
        bot.send_message(message.from_user.id, phrases[9], reply_markup=markup)
    else:
        # data is incorrect
        msg = bot.send_message(message.from_user.id,
                         functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                             'add task'][8])

        logger.info('User entered incorrect data. Trying again...')
        bot.register_next_step_handler(msg, priority_step)

    db_connection.commit()

    db_cursor.close()
    db_connection.close()


@bot.message_handler(func=lambda x: x.text == 'ВИДАЛИТИ TODO СПИСОК' or x.text == 'DELETE TODO LIST' or x.text == 'УДАЛИТЬ TODO СПИСОК')
def delete_list(message):
    if message.chat.type == 'private':
        db_connection = sqlite3.connect(DB_NAME)
        db_cursor = db_connection.cursor()

        logger.info(f'User with id - {message.from_user.id} is trying to access deletelist keyboard.')

        # getting a data from a db (format - [(id1, time1, name1),...,(idn, timen, namen), ])
        lists = functions.get_lists_db(db_cursor, message.from_user.id)

        # user has no lists
        if not len(lists):
            bot.send_message(message.from_user.id,
                             functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)[
                                 'get lists'][0])
            logger.info('User has no lists.')
        else:
            i = 0
            phrases = functions.get_lang_profile_chat(db_cursor, message.from_user.id, PREFERRED_LANGUAGE)['delete list'][0]

            # setting a keyboard
            markup = types.InlineKeyboardMarkup()
            markup.row_width = 4

            while i < len(lists):
                markup.add(types.InlineKeyboardButton(lists[i][2],
                                                      callback_data=f'deletelist {lists[i][0]}'))
                i += 1

            bot.send_message(message.from_user.id, phrases, reply_markup=markup)

            logger.info('Success.')

        db_cursor.close()
        db_connection.close()


if __name__ == '__main__':
    bot.polling()