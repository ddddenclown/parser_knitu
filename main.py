from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
import aiohttp
from bs4 import BeautifulSoup
import re
from datetime import datetime, timedelta
import sqlite3
import asyncio

# Состояния диалога
MAIN_MENU, FAVORITES, FACULTY, LEVEL, COURSE, GROUP, ADD_FAVORITE, DAYS_SELECTION, FAVORITE_ACTION = range(9)

token_tg = "your_token"

FACULTY_MAP = {
    "ИХТИ": "210",
    "ИХНМ": "224",
    "ИУИ": "243",
    "ИНХН": "256",
    "ИП": "283",
    "ИППБТ": "297",
    "ИТЛПМД": "306",
    "ИУАИТ": "320"
}


# Инициализация БД
def init_db():
    conn = sqlite3.connect('favorites.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS favorites (
            user_id INTEGER NOT NULL,
            group_name TEXT NOT NULL,
            group_code TEXT NOT NULL,
            faculty TEXT NOT NULL,
            PRIMARY KEY (user_id, group_code)
        )
    ''')
    conn.commit()
    conn.close()


init_db()


async def add_favorite_group(user_id: int, group_name: str, group_code: str, faculty: str):
    def sync_add():
        conn = sqlite3.connect('favorites.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO favorites 
            VALUES (?, ?, ?, ?)
        ''', (user_id, group_name, group_code, faculty))
        conn.commit()
        conn.close()

    await asyncio.to_thread(sync_add)

async def get_favorite_groups(user_id: int) -> list:
    def sync_get():
        conn = sqlite3.connect('favorites.db')
        cursor = conn.cursor()
        cursor.execute('''
            SELECT group_name, group_code, faculty 
            FROM favorites WHERE user_id = ?
        ''', (user_id,))
        result = cursor.fetchall()
        conn.close()
        return result

    return await asyncio.to_thread(sync_get)


async def remove_favorite_group(user_id: int, group_code: str):
    def sync_remove():
        conn = sqlite3.connect('favorites.db')
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM favorites 
            WHERE user_id = ? AND group_code = ?
        ''', (user_id, group_code))
        conn.commit()
        conn.close()

    await asyncio.to_thread(sync_remove)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["Избранные группы", "Другие группы"]]
    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        one_time_keyboard=True,
        resize_keyboard=True
    )
    await update.message.reply_text(
        "Выберите раздел:",
        reply_markup=reply_markup
    )
    return MAIN_MENU


async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "Избранные группы":
        user_id = update.effective_user.id
        favorites = await get_favorite_groups(user_id)

        if not favorites:
            await update.message.reply_text("У вас пока нет избранных групп.")
            keyboard = [["Другие группы", "Назад"]]
            reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
            await update.message.reply_text("Выберите действие:", reply_markup=reply_markup)
            return MAIN_MENU

        group_names = [group[0] for group in favorites]
        keyboard = [group_names[i:i + 2] for i in range(0, len(group_names), 2)]
        keyboard.append(["Назад"])
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Выберите группу из избранных:", reply_markup=reply_markup)
        context.user_data['favorites'] = favorites
        return FAVORITES

    elif choice == "Другие группы":
        faculties = list(FACULTY_MAP.keys())
        keyboard = [faculties[i:i + 2] for i in range(0, len(faculties), 2)]
        reply_markup = ReplyKeyboardMarkup(
            keyboard,
            one_time_keyboard=True,
            resize_keyboard=True
        )
        await update.message.reply_text("Выберите факультет:", reply_markup=reply_markup)
        return FACULTY

    await update.message.reply_text("Пожалуйста, выберите раздел из предложенных.")
    return MAIN_MENU


async def handle_favorite(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group_name = update.message.text
    favorites = context.user_data.get('favorites', [])

    if group_name == "Назад":
        return await start(update, context)

    selected = next((group for group in favorites if group[0] == group_name), None)
    if not selected:
        await update.message.reply_text("Группа не найдена.")
        return await start(update, context)

    context.user_data['current_group'] = {
        'name': selected[0],
        'code': selected[1],
        'faculty': selected[2]
    }

    # Предложение действия для избранной группы
    keyboard = [["Показать расписание", "Удалить из избранного"], ["Назад"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите действие с группой:",
        reply_markup=reply_markup
    )
    return FAVORITE_ACTION


async def handle_favorite_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "Назад":
        return await start(update, context)

    if choice == "Показать расписание":
        # Переход к выбору периода
        keyboard = [["1 день", "3 дня"], ["Вся неделя"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(
            "Выберите период отображения расписания:",
            reply_markup=reply_markup
        )
        return DAYS_SELECTION

    if choice == "Удалить из избранного":
        user_id = update.effective_user.id
        group_data = context.user_data['current_group']
        await remove_favorite_group(user_id, group_data['code'])
        await update.message.reply_text("✅ Группа успешно удалена из избранных!")
        return await start(update, context)

    await update.message.reply_text("Неизвестное действие. Пожалуйста, выберите из предложенных.")
    return FAVORITE_ACTION


async def get_faculty(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    faculty_name = update.message.text.strip().upper()

    if faculty_name not in FACULTY_MAP:
        faculties = list(FACULTY_MAP.keys())
        keyboard = [faculties[i:i + 2] for i in range(0, len(faculties), 2)]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Неверный факультет. Выберите из списка:", reply_markup=reply_markup)
        return FACULTY

    context.user_data['faculty'] = FACULTY_MAP[faculty_name]
    levels = ['Бакалавриат', 'Специалитет', 'Магистратура']
    keyboard = [levels[i:i + 2] for i in range(0, len(levels), 2)]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите уровень образования:", reply_markup=reply_markup)
    return LEVEL


async def get_level(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    level = update.message.text.lower()
    valid_levels = {'бакалавриат', 'специалитет', 'магистратура'}

    if level not in valid_levels:
        await update.message.reply_text("Неверный уровень образования. Выберите из списка:")
        return LEVEL

    context.user_data['level'] = level
    courses = [str(i) for i in range(1, 6)]
    keyboard = [courses[i:i + 3] for i in range(0, len(courses), 3)]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Выберите курс:", reply_markup=reply_markup)
    return COURSE


async def get_course(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    course = update.message.text.strip()

    if not course.isdigit() or int(course) not in range(1, 6):
        await update.message.reply_text("Неверный курс. Выберите от 1 до 5:")
        return COURSE

    context.user_data['course'] = course
    faculty = context.user_data['faculty']
    level = context.user_data['level']
    groups = await get_groups(faculty, level, course)

    if not groups:
        await update.message.reply_text("Группы не найдены. Попробуйте снова.")
        return await start(update, context)

    context.user_data['available_groups'] = groups
    group_list = "\n".join(groups.keys())
    await update.message.reply_text(
        f"Доступные группы:\n{group_list}\nВведите название группы:",
        reply_markup=ReplyKeyboardRemove()
    )
    return GROUP


async def get_groups(faculty: str, level: str, course: str) -> dict:
    level_map = {
        'бакалавриат': '40420,40421',
        'специалитет': '40420,40421',
        'магистратура': '40422'
    }
    l_param = level_map.get(level.lower(), '')

    url = f"https://www.kstu.ru/www_GFgrid.jsp?dt=2024-10-17&f={faculty}&k={course}&t=0&l={l_param}&v=0"

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as response:
                html = await response.text()
                soup = BeautifulSoup(html, 'html.parser')
                groups = {}
                for div in soup.select('form[name="form2"] .my_hashtag'):
                    group_name = div.text.strip()
                    onclick = div.get('onclick', '')
                    if match := re.search(r"g\.value='(\d+)'", onclick):
                        groups[group_name] = match.group(1)
                return groups
        except:
            return {}


async def get_group(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_input = update.message.text.strip()
    groups = context.user_data.get('available_groups', {})
    group_code = groups.get(user_input)

    if not group_code:
        await update.message.reply_text("Группа не найдена. Введите правильно:")
        return GROUP

    context.user_data['current_group'] = {
        'name': user_input,
        'code': group_code,
        'faculty': context.user_data['faculty']
    }

    # Выбор периода отображения
    keyboard = [["1 день", "3 дня"], ["Вся неделя"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Выберите период отображения расписания:",
        reply_markup=reply_markup
    )
    return DAYS_SELECTION


async def select_days(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    days_map = {
        "1 день": 1,
        "3 дня": 3,
        "Вся неделя": 7
    }

    if choice not in days_map:
        await update.message.reply_text("Неверный выбор. Попробуйте снова:")
        return DAYS_SELECTION

    context.user_data['days_to_show'] = days_map[choice]
    return await show_schedule(update, context)


async def show_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    group_data = context.user_data['current_group']
    days = context.user_data.get('days_to_show', 3)
    faculty = group_data['faculty']
    group_code = group_data['code']
    today = datetime.now().date()

    async with aiohttp.ClientSession() as session:
        try:
            url = f"https://www.kstu.ru/www_Ggrid.jsp?d={today}&f={faculty}&g={group_code}"
            async with session.get(url) as response:
                html = await response.text()
                schedule = parse_schedule(html)
                message = format_schedule(schedule, days)
                await update.message.reply_text(message, reply_markup=ReplyKeyboardRemove())
        except Exception as e:
            await update.message.reply_text("Ошибка загрузки расписания")

    # Предложение добавить в избранное
    user_id = update.effective_user.id
    favorites = await get_favorite_groups(user_id)
    if not any(g[1] == group_code for g in favorites):
        keyboard = [["Добавить в избранное", "Пропустить"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Добавить группу в избранные?", reply_markup=reply_markup)
        return ADD_FAVORITE

    return await start(update, context)


def format_schedule(schedule: dict, days: int = 3) -> str:
    message = []
    today = datetime.now().date()

    for delta in range(days):
        current_date = today + timedelta(days=delta)
        lessons = schedule.get(current_date, [])

        if lessons:
            message.append(f"📅 {current_date.strftime('%d.%m.%Y %A')}")
            for lesson in lessons:
                message.append(
                    f"⏰ {lesson['time']}\n"
                    f"📚 {lesson['subject']}\n"
                    f"📍 {lesson['room']}\n"
                    f"👨🏫 {lesson['teacher']}\n"
                )
            message.append("")
            message.append("-----------------------------------------")

    return "\n".join(message) if message else "Расписание на выбранный период пусто."


async def add_favorite_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    choice = update.message.text
    if choice == "Добавить в избранное":
        user_id = update.effective_user.id
        group_data = context.user_data['current_group']
        await add_favorite_group(user_id, group_data['name'], group_data['code'], group_data['faculty'])
        await update.message.reply_text("✅ Группа добавлена в избранные!")
    else:
        await update.message.reply_text("Группа не добавлена.")

    return await start(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Действие отменено.", reply_markup=ReplyKeyboardRemove())
    return ConversationHandler.END


def parse_schedule(html: str) -> dict:
    soup = BeautifulSoup(html, 'html.parser')
    schedule = {}
    table = soup.find('table', class_='brstu-table')

    if not table:
        return {}

    date_cells = table.find('tr', bgcolor="#FFFFCC").find_all('td')[1:]
    dates = [datetime.strptime(cell.text.strip().split()[0], "%d.%m.%Y").date() for cell in date_cells]

    for row in table.find_all('tr'):
        time_cell = row.find('td', width="100")
        if not time_cell:
            continue

        time_info = time_cell.text.strip().split('\n')[0].strip()
        lesson_cells = row.find_all('td')[1:]

        for i, cell in enumerate(lesson_cells):
            current_date = dates[i]
            lesson_data = parse_lesson_cell(cell)

            if current_date not in schedule:
                schedule[current_date] = []
            schedule[current_date].append({
                'time': time_info,
                **lesson_data
            })

    return schedule


def parse_lesson_cell(cell):
    content = list(cell.stripped_strings)
    if not content or 'Нет пары' in content[0]:
        return {'subject': 'Нет пары', 'room': '-', 'teacher': '-'}

    room = content[0]
    subject = content[1] if len(content) > 1 else '-'
    teachers = [a.text.strip() for a in cell.find_all('a')]

    return {
        'subject': subject,
        'room': room,
        'teacher': ', '.join(teachers) if teachers else '-'
    }


def main() -> None:
    application = Application.builder().token(token_tg).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            MAIN_MENU: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_menu)],
            FAVORITES: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_favorite)],
            FACULTY: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_faculty)],
            LEVEL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_level)],
            COURSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_course)],
            GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_group)],
            ADD_FAVORITE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_favorite_choice)],
            DAYS_SELECTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, select_days)],
            FAVORITE_ACTION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_favorite_action)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
        allow_reentry=True
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == '__main__':
    main()
