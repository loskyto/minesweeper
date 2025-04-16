import os
from flask import Flask, request
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import random

app = Flask(__name__)
bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN"))
dp = Dispatcher(bot)

# Настройки игры
BOARD_SIZE = 8
MINES_COUNT = 10

# Стимпанк-эмодзи
EMPTY = "🛠"  # Неоткрытая клетка
MINE = "💥"   # Мина
FLAG = "⚙️"   # Флажок
NUMBERS = ["0️⃣", "1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣"]

# Игровые данные (храним в памяти)
user_games = {}  # {user_id: {"board": [], "revealed": [], "flags": set()}}

# Создание поля
def create_board():
    board = [[0 for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
    mines = set()

    # Расставляем мины
    while len(mines) < MINES_COUNT:
        x, y = random.randint(0, BOARD_SIZE-1), random.randint(0, BOARD_SIZE-1)
        if (x, y) not in mines:
            mines.add((x, y))
            board[x][y] = -1

    # Заполняем цифры (сколько мин вокруг)
    for x in range(BOARD_SIZE):
        for y in range(BOARD_SIZE):
            if board[x][y] == -1:
                continue
            count = 0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE and board[nx][ny] == -1:
                        count += 1
            board[x][y] = count
    return board

# Генерация клавиатуры
def generate_keyboard(user_id):
    game_data = user_games[user_id]
    board = game_data["board"]
    revealed = game_data["revealed"]
    flags = game_data["flags"]

    keyboard = InlineKeyboardMarkup(row_width=BOARD_SIZE)
    for x in range(BOARD_SIZE):
        row = []
        for y in range(BOARD_SIZE):
            if (x, y) in flags:
                btn = FLAG
                cb_data = f"unflag_{x}_{y}"
            elif revealed[x][y]:
                if board[x][y] == -1:
                    btn = MINE
                else:
                    btn = NUMBERS[board[x][y]]
                cb_data = f"open_{x}_{y}"
            else:
                btn = EMPTY
                cb_data = f"flag_{x}_{y}"
            row.append(InlineKeyboardButton(btn, callback_data=cb_data))
        keyboard.add(*row)
    return keyboard

# Рекурсивное открытие клеток
def reveal_cells(x, y, board, revealed):
    if revealed[x][y]:
        return
    revealed[x][y] = True
    if board[x][y] != 0:
        return
    for dx in [-1, 0, 1]:
        for dy in [-1, 0, 1]:
            nx, ny = x + dx, y + dy
            if 0 <= nx < BOARD_SIZE and 0 <= ny < BOARD_SIZE:
                reveal_cells(nx, ny, board, revealed)

# Проверка победы
def check_win(game_data):
    flags = game_data["flags"]
    board = game_data["board"]
    mines = {(x, y) for x in range(BOARD_SIZE) for y in range(BOARD_SIZE) if board[x][y] == -1}
    return flags == mines

# Команда /start
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    user_id = message.from_user.id
    user_games[user_id] = {
        "board": create_board(),
        "revealed": [[False for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)],
        "flags": set()
    }
    await message.reply(
        "🔧 *Добро пожаловать в Steampunk Minesweeper!*\n\n"
        "🛠 — закрытая клетка\n"
        "⚙️ — флажок\n"
        "💥 — мина\n\n"
        "Нажмите на клетку, чтобы открыть её. Удерживайте для установки флажка.",
        reply_markup=generate_keyboard(user_id),
        parse_mode="Markdown"
    )

# Обработка нажатий
@dp.callback_query_handler(lambda c: True)
async def handle_click(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id not in user_games:
        await callback_query.answer("Игра не начата! Напишите /start")
        return

    action, x, y = callback_query.data.split("_")
    x, y = int(x), int(y)
    game_data = user_games[user_id]
    board = game_data["board"]
    revealed = game_data["revealed"]
    flags = game_data["flags"]

    if action == "flag":
        flags.add((x, y))
    elif action == "unflag":
        flags.discard((x, y))
    elif action == "open":
        if board[x][y] == -1:
            # Проигрыш (открыли мину)
            revealed = [[True for _ in range(BOARD_SIZE)] for _ in range(BOARD_SIZE)]
            await callback_query.message.edit_text(
                "💥 *БАБАХ!* Ты наступил на мину!\n\n/gameover",
                reply_markup=generate_keyboard(user_id),
                parse_mode="Markdown"
            )
            return
        else:
            reveal_cells(x, y, board, revealed)

    if check_win(game_data):
        await callback_query.message.edit_text(
            "🎉 *Победа!* Ты обезвредил все мины!\n\n/start — сыграть ещё",
            reply_markup=generate_keyboard(user_id),
            parse_mode="Markdown"
        )
    else:
        await callback_query.message.edit_reply_markup(generate_keyboard(user_id))
    await callback_query.answer()

# Вебхук для Vercel
@app.route('/webhook', methods=['POST'])
async def webhook():
    update = types.Update(**request.json)
    await dp.process_update(update)
    return 'ok'

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)

@app.route('/')
def home():
    return "Бот работает! Используйте /webhook для Telegram."

if __name__ == '__main__':
    app.run(debug=True)
