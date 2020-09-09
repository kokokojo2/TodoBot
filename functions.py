import codecs
import json

from datetime import datetime
from datetime import timedelta
from telebot import types


def get_dialog_profile(language):
    if language == 'UA':
        filename = 'dialog_ua.json'
    elif language == 'RU':
        filename = 'dialog_ru.json'
    elif language == 'EN':
        filename = 'dialog_en.json'
    else:
        return None

    raw_json = codecs.open(filename, encoding='utf-8').read()
    raw_json = codecs.decode(raw_json.encode(), 'utf-8-sig')
    return json.loads(raw_json)


def get_lang_profile_chat(cursor, tele_id, preferred_lang):
    cursor.execute('SELECT language FROM Users WHERE tele_id = ?', (tele_id,))
    lang = cursor.fetchone()
    try:
        lang = lang[0]
    except TypeError:
        print('typeerror')
        lang = preferred_lang

    return get_dialog_profile(lang)


def get_language(cursor, tele_id):
    cursor.execute('SELECT language FROM Users WHERE tele_id = ?', (tele_id,))
    return cursor.fetchone()[0]


def get_lists_db(cursor, tele_id):
    cursor.execute('SELECT id FROM Users WHERE tele_id = ?', (tele_id, ))
    try:
        user_id = cursor.fetchone()[0]
    except TypeError:
        return None

    cursor.execute('SELECT id, time, name FROM Sheets WHERE user_id = ?', (user_id, ))
    return cursor.fetchall()


def user_id_db(cursor, tele_id):
    cursor.execute('SELECT id FROM Users WHERE tele_id = ?', (tele_id,))
    return cursor.fetchone()[0]


def last_callback(cursor, tele_id):
    cursor.execute('SELECT last_callback FROM Users WHERE tele_id = ?', (tele_id,))
    return cursor.fetchone()[0]


def get_timestamp(text):
    try:
        date = datetime.strptime(text, '%d.%m.%Y')
        date += timedelta(days=1)
        stmp = datetime.timestamp(date)
        if stmp - datetime.timestamp(datetime.now()) > 0:
            return stmp
        else:
            return None
    except ValueError:
        return None


def get_sheet_id(cursor, tele_id, sheet_name):
    user_id = user_id_db(cursor, tele_id)

    cursor.execute('SELECT id FROM Sheets WHERE name = ? AND user_id = ?', (sheet_name, user_id))
    return cursor.fetchone()[0]


def task_parser(task):
    result = ''

    status = task[2]
    deadline = task[1]

    # in case if deadline is failed
    if status != 1 and float(deadline) - datetime.timestamp(datetime.now()) < 0:
        status = 2

    # dealing with status
    if status == 0:
        result += '🔄'
    elif status == 1:
        result += '✅'
    elif status == 2:
        result += '❌'

    # dealing with priority
    if task[3] == 0:
        result += '⬜'
    elif task[3] == 1:
        result += '🟩'
    elif task[3] == 2:
        result += '🟨'
    elif task[3] == 3:
        result += '🟥'

    result += '*' + task[0] + '*'

    deadline_data = datetime.fromtimestamp(deadline)
    deadline_day = deadline_data.day
    deadline_day -= 1
    delta = deadline_data - datetime.now()

    if delta.days == 1:
        phrase = 'day'
    else:
        phrase = 'days'

    result += '⏱' + f'{deadline_day}.{deadline_data.strftime("%m.%Y")}⏱({delta.days + 1} {phrase})'
    return result


def tasks_buttons(cursor, sheet_name, tele_id, mode):

    sheet_id = get_sheet_id(cursor, tele_id, sheet_name.replace("_", " "))
    language = get_language(cursor, tele_id)

    cursor.execute('SELECT task, id  FROM Tasks WHERE sheet_id = ?', (sheet_id,))
    tasks = cursor.fetchall()

    markup = types.InlineKeyboardMarkup()

    for task in tasks:
        markup.add(types.InlineKeyboardButton(text=task[0], callback_data=f'{mode} {task[1]} {sheet_id}'))

    lists = get_lists_db(cursor, tele_id)

    i = 0
    while i < len(lists):
        if lists[i][2] == sheet_name.replace("_", " "):
            break
        i += 1

    markup.add(types.InlineKeyboardButton(text=get_dialog_profile(language)['markdone'][1], callback_data=f'getlist {sheet_name} {i}'))
    return markup


def list_existence(sheet_name, cursor, user_id):

    exists = True
    try:
        get_sheet_id(cursor, user_id, sheet_name)
    except TypeError:
        exists = False

    return exists


if __name__ == '__main__':
    data = '12.07.2020'
    print(get_timestamp(data), datetime.fromtimestamp(get_timestamp(data)))
