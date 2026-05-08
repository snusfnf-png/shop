import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyParameters
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "tntks")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REVIEWS_CHANNEL = "https://t.me/urbiex"
FREE_CHANNEL = "https://t.me/carzdrop"
FREE_CHANNEL_ID = os.getenv("FREE_CHANNEL_ID", "@carzdrop")


class TicketStates(StatesGroup):
    pack_name = State()
    pack_link = State()
    pack_nick = State()
    pack_style = State()
    pack_style_custom = State()


bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# ─── Keyboards ───────────────────────────────────────────────────────────────

def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🟢 Сделать пак", callback_data="make_pack")],
        [InlineKeyboardButton(text="🎁 Получить пак бесплатно", callback_data="free_pack")],
        [InlineKeyboardButton(text="🔵 Отзывы", url=REVIEWS_CHANNEL)],
    ])

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel_ticket")]
    ])

def style_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚫⚪ Стандартный (чёрно-белый)", callback_data="style_standard")],
        [InlineKeyboardButton(text="✏️ Описать свой стиль", callback_data="style_custom")],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel_ticket")],
    ])

def check_sub_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📢 Подписаться на канал", url=FREE_CHANNEL)],
        [InlineKeyboardButton(text="✅ Я подписался", callback_data="check_sub")],
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")],
    ])

def back_to_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Главное меню", callback_data="main_menu")]
    ])

# ─── Helpers ─────────────────────────────────────────────────────────────────

async def check_subscription(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(FREE_CHANNEL_ID, user_id)
        return member.status not in ("left", "kicked", "banned")
    except Exception as e:
        logger.warning(f"Sub check error: {e}")
        return False

async def send_ticket_to_admin(user: dict, ticket: dict, message: Message):
    text = (
        f"🎫 <b>НОВЫЙ ТИКЕТ</b>\n\n"
        f"👤 <b>Пользователь:</b> {user['name']}\n"
        f"🆔 <b>ID:</b> <code>{user['id']}</code>\n"
        f"📱 <b>Username:</b> @{user['username']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>Название пака:</b> {ticket['name']}\n"
        f"🔗 <b>Ссылка на пак:</b> {ticket['link']}\n"
        f"✏️ <b>Ник на эмодзи:</b> {ticket['nick']}\n"
        f"🎨 <b>Вид пака:</b> {ticket['style']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>Ответьте на это сообщение со ссылкой на готовый пак — она автоматически уйдёт пользователю.</i>"
    )
    try:
        sent = await bot.send_message(ADMIN_ID, text)
        # Save mapping: admin message_id → user_id
        ticket_map[sent.message_id] = user['id']
        logger.info(f"Ticket sent to admin, msg_id={sent.message_id}, user_id={user['id']}")
    except Exception as e:
        logger.error(f"Failed to send ticket to admin: {e}")
        await message.answer(
            "⚠️ Не удалось отправить тикет администратору. Попробуйте позже.",
            reply_markup=back_to_menu_kb()
        )

# In-memory storage for ticket mapping: admin_msg_id -> user_id
ticket_map: dict[int, int] = {}

# ─── Handlers ────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = message.from_user.first_name or "пользователь"
    await message.answer(
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Добро пожаловать в <b>EMOJI PAK</b> — сервис создания уникальных эмодзи паков с твоим ником! 🎨\n\n"
        f"Выбери нужное действие:",
        reply_markup=main_menu_kb()
    )

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    name = callback.from_user.first_name or "пользователь"
    await callback.message.edit_text(
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Добро пожаловать в <b>EMOJI PAK</b> — сервис создания уникальных эмодзи паков с твоим ником! 🎨\n\n"
        f"Выбери нужное действие:",
        reply_markup=main_menu_kb()
    )
    await callback.answer()

# ─── Make Pack ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "make_pack")
async def cb_make_pack(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TicketStates.pack_name)
    await callback.message.edit_text(
        "📦 <b>Шаг 1 из 4 — Название пака</b>\n\n"
        "Введи желаемое название для твоего эмодзи пака:\n\n"
        "<i>Например: MyPackName или CoolEmojis</i>",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@dp.message(TicketStates.pack_name)
async def step_pack_name(message: Message, state: FSMContext):
    await state.update_data(pack_name=message.text.strip())
    await state.set_state(TicketStates.pack_link)
    await message.answer(
        "🔗 <b>Шаг 2 из 4 — Ссылка на пак</b>\n\n"
        "Отправь ссылку на существующий пак или укажи желаемый адрес:\n\n"
        "<i>Например: t.me/addemoji/packname</i>",
        reply_markup=cancel_kb()
    )

@dp.message(TicketStates.pack_link)
async def step_pack_link(message: Message, state: FSMContext):
    await state.update_data(pack_link=message.text.strip())
    await state.set_state(TicketStates.pack_nick)
    await message.answer(
        "✏️ <b>Шаг 3 из 4 — Ник на эмодзи</b>\n\n"
        "Введи ник или надпись, которая будет на эмодзи:",
        reply_markup=cancel_kb()
    )

@dp.message(TicketStates.pack_nick)
async def step_pack_nick(message: Message, state: FSMContext):
    await state.update_data(pack_nick=message.text.strip())
    await state.set_state(TicketStates.pack_style)
    await message.answer(
        "🎨 <b>Шаг 4 из 4 — Вид пака</b>\n\n"
        "Выбери стиль оформления эмодзи пака:",
        reply_markup=style_kb()
    )

@dp.callback_query(TicketStates.pack_style, F.data == "style_standard")
async def step_style_standard(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    ticket = {
        "name": data.get("pack_name", "—"),
        "link": data.get("pack_link", "—"),
        "nick": data.get("pack_nick", "—"),
        "style": "⚫⚪ Стандартный (чёрно-белый)",
    }
    user = {
        "id": callback.from_user.id,
        "name": callback.from_user.full_name,
        "username": callback.from_user.username or "нет",
    }

    await send_ticket_to_admin(user, ticket, callback.message)
    await callback.message.edit_text(
        "✅ <b>Заявка отправлена!</b>\n\n"
        f"📦 Пак: <b>{ticket['name']}</b>\n"
        f"🎨 Стиль: {ticket['style']}\n\n"
        "Администратор уже получил твой тикет и скоро приступит к работе. "
        "Как только пак будет готов — ты получишь ссылку прямо здесь! 🚀",
        reply_markup=back_to_menu_kb()
    )
    await callback.answer("✅ Тикет отправлен!")

@dp.callback_query(TicketStates.pack_style, F.data == "style_custom")
async def step_style_custom_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TicketStates.pack_style_custom)
    await callback.message.edit_text(
        "✏️ <b>Опиши свой стиль</b>\n\n"
        "Напиши подробное описание желаемого вида пака.\n\n"
        "<i>Например: синие тона, аниме-стиль, с золотыми деталями</i>",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@dp.message(TicketStates.pack_style_custom)
async def step_style_custom_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    ticket = {
        "name": data.get("pack_name", "—"),
        "link": data.get("pack_link", "—"),
        "nick": data.get("pack_nick", "—"),
        "style": f"✏️ Свой стиль: {message.text.strip()}",
    }
    user = {
        "id": message.from_user.id,
        "name": message.from_user.full_name,
        "username": message.from_user.username or "нет",
    }

    await send_ticket_to_admin(user, ticket, message)
    await message.answer(
        "✅ <b>Заявка отправлена!</b>\n\n"
        f"📦 Пак: <b>{ticket['name']}</b>\n"
        f"🎨 Стиль: {ticket['style']}\n\n"
        "Администратор уже получил твой тикет и скоро приступит к работе. "
        "Как только пак будет готов — ты получишь ссылку прямо здесь! 🚀",
        reply_markup=back_to_menu_kb()
    )

# ─── Cancel ──────────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "cancel_ticket")
async def cb_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Заявка отменена.</b>\n\nВозвращаемся в главное меню:",
        reply_markup=main_menu_kb()
    )
    await callback.answer("Отменено")

# ─── Free Pack ───────────────────────────────────────────────────────────────

@dp.callback_query(F.data == "free_pack")
async def cb_free_pack(callback: CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        await callback.message.edit_text(
            "🎁 <b>Поздравляем!</b>\n\n"
            "Ты подписан на канал и можешь получить эмодзи пак <b>бесплатно</b>! 🎉\n\n"
            "Напиши напрямую администратору: @tntks и скажи, что хочешь получить бесплатный пак. "
            "Не забудь отправить скрин подписки!",
            reply_markup=back_to_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "🎁 <b>Получи эмодзи пак бесплатно!</b>\n\n"
            "Для этого нужно подписаться на наш канал.\n\n"
            "1️⃣ Нажми кнопку <b>«Подписаться на канал»</b>\n"
            "2️⃣ Подпишись на канал\n"
            "3️⃣ Нажми <b>«Я подписался»</b> для проверки",
            reply_markup=check_sub_kb()
        )
    await callback.answer()

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery):
    is_subscribed = await check_subscription(callback.from_user.id)
    if is_subscribed:
        await callback.message.edit_text(
            "✅ <b>Подписка подтверждена!</b>\n\n"
            "Ты подписан на канал и можешь получить эмодзи пак <b>бесплатно</b>! 🎉\n\n"
            "Напиши напрямую администратору: @tntks и скажи, что хочешь получить бесплатный пак. "
            "Не забудь отправить скрин подписки!",
            reply_markup=back_to_menu_kb()
        )
        await callback.answer("✅ Подписка подтверждена!")
    else:
        await callback.answer("❌ Ты ещё не подписан на канал!", show_alert=True)

# ─── Admin reply handler ──────────────────────────────────────────────────────

@dp.message(F.reply_to_message)
async def handle_admin_reply(message: Message):
    # Only process replies from admin
    if message.from_user.id != ADMIN_ID:
        return

    replied_msg_id = message.reply_to_message.message_id
    user_id = ticket_map.get(replied_msg_id)

    if not user_id:
        return

    try:
        await bot.send_message(
            user_id,
            f"🎉 <b>Твой эмодзи пак готов!</b>\n\n"
            f"{message.text or message.caption or ''}",
            reply_markup=back_to_menu_kb()
        )
        await message.reply("✅ Сообщение отправлено пользователю!")
        # Remove from map after delivery
        del ticket_map[replied_msg_id]
    except Exception as e:
        logger.error(f"Failed to forward to user {user_id}: {e}")
        await message.reply(f"⚠️ Не удалось отправить пользователю: {e}")

# ─── Main ─────────────────────────────────────────────────────────────────────

async def main():
    logger.info("Starting bot...")
    await dp.start_polling(bot, skip_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
    
