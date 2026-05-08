import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
)
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
REVIEWS_CHANNEL = "https://t.me/urbiex"
FREE_CHANNEL = "https://t.me/carzdrop"
FREE_CHANNEL_ID = os.getenv("FREE_CHANNEL_ID", "@carzdrop")

# ─── States ──────────────────────────────────────────────────────────────────

class TicketStates(StatesGroup):
    pack_name = State()
    pack_link = State()
    pack_nick = State()
    pack_style = State()
    pack_style_custom = State()

class FreeTicketStates(StatesGroup):
    pack_name = State()
    pack_link = State()
    pack_nick = State()
    pack_style = State()
    pack_style_custom = State()

# ─── Bot & Dispatcher ────────────────────────────────────────────────────────

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher(storage=MemoryStorage())

# In-memory: admin_msg_id -> user_id
ticket_map: dict[int, int] = {}

# In-memory: set of user_ids who already used free pack
free_pack_used: set[int] = set()

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

def cancel_free_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data="cancel_free_ticket")]
    ])

def style_kb(free: bool = False) -> InlineKeyboardMarkup:
    cancel_cb = "cancel_free_ticket" if free else "cancel_ticket"
    style_std = "free_style_standard" if free else "style_standard"
    style_cst = "free_style_custom" if free else "style_custom"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚫⚪ Стандартный (чёрно-белый)", callback_data=style_std)],
        [InlineKeyboardButton(text="✏️ Описать свой стиль", callback_data=style_cst)],
        [InlineKeyboardButton(text="❌ Отменить заявку", callback_data=cancel_cb)],
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

def welcome_text(name: str) -> str:
    return (
        f"👋 Привет, <b>{name}</b>!\n\n"
        f"Создавай здесь пак с твоим ником, пример: "
        f"https://t.me/addemoji/floppers_by_ninenebot"
    )

def format_ticket(user: dict, ticket: dict, is_free: bool = False) -> str:
    label = "🎁 БЕСПЛАТНЫЙ ТИКЕТ" if is_free else "🎫 НОВЫЙ ТИКЕТ"
    return (
        f"{label}\n\n"
        f"👤 <b>Пользователь:</b> {user['name']}\n"
        f"🆔 <b>ID:</b> <code>{user['id']}</code>\n"
        f"📱 <b>Username:</b> @{user['username']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📦 <b>Название пака:</b>\n<code>{ticket['name']}</code>\n\n"
        f"🔗 <b>Ссылка на пак:</b>\n<code>{ticket['link']}</code>\n\n"
        f"✏️ <b>Ник на эмодзи:</b>\n<code>{ticket['nick']}</code>\n\n"
        f"🎨 <b>Вид пака:</b> {ticket['style']}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 <i>Ответьте на это сообщение со ссылкой на готовый пак — "
        f"она автоматически уйдёт пользователю.</i>"
    )

async def send_ticket_to_admin(user: dict, ticket: dict, is_free: bool = False) -> bool:
    text = format_ticket(user, ticket, is_free)
    try:
        sent = await bot.send_message(ADMIN_ID, text)
        ticket_map[sent.message_id] = user['id']
        logger.info(f"Ticket sent msg_id={sent.message_id} user_id={user['id']} free={is_free}")
        return True
    except Exception as e:
        logger.error(f"Failed to send ticket to admin: {e}")
        return False

# ─── /start ──────────────────────────────────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    name = message.from_user.first_name or "пользователь"
    await message.answer(welcome_text(name), reply_markup=main_menu_kb())

@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    name = callback.from_user.first_name or "пользователь"
    await callback.message.edit_text(welcome_text(name), reply_markup=main_menu_kb())
    await callback.answer()

# ─── Make Pack (paid) ────────────────────────────────────────────────────────

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
async def paid_step_name(message: Message, state: FSMContext):
    await state.update_data(pack_name=message.text.strip())
    await state.set_state(TicketStates.pack_link)
    await message.answer(
        "🔗 <b>Шаг 2 из 4 — Ссылка на пак</b>\n\n"
        "Отправь ссылку на существующий пак или укажи желаемый адрес:\n\n"
        "<i>Например: t.me/addemoji/packname</i>",
        reply_markup=cancel_kb()
    )

@dp.message(TicketStates.pack_link)
async def paid_step_link(message: Message, state: FSMContext):
    await state.update_data(pack_link=message.text.strip())
    await state.set_state(TicketStates.pack_nick)
    await message.answer(
        "✏️ <b>Шаг 3 из 4 — Ник на эмодзи</b>\n\n"
        "Введи ник или надпись, которая будет на эмодзи:",
        reply_markup=cancel_kb()
    )

@dp.message(TicketStates.pack_nick)
async def paid_step_nick(message: Message, state: FSMContext):
    await state.update_data(pack_nick=message.text.strip())
    await state.set_state(TicketStates.pack_style)
    await message.answer(
        "🎨 <b>Шаг 4 из 4 — Вид пака</b>\n\n"
        "Выбери стиль оформления эмодзи пака:",
        reply_markup=style_kb(free=False)
    )

@dp.callback_query(TicketStates.pack_style, F.data == "style_standard")
async def paid_style_standard(callback: CallbackQuery, state: FSMContext):
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
    ok = await send_ticket_to_admin(user, ticket, is_free=False)
    if ok:
        await callback.message.edit_text(
            "✅ <b>Заявка отправлена!</b>\n\n"
            f"📦 Пак: <b>{ticket['name']}</b>\n"
            f"🎨 Стиль: {ticket['style']}\n\n"
            "Администратор получил твой тикет и скоро приступит к работе. "
            "Как только пак будет готов — ты получишь ссылку прямо здесь! 🚀",
            reply_markup=back_to_menu_kb()
        )
    else:
        await callback.message.edit_text(
            "⚠️ Не удалось отправить тикет. Попробуй позже.",
            reply_markup=back_to_menu_kb()
        )
    await callback.answer()

@dp.callback_query(TicketStates.pack_style, F.data == "style_custom")
async def paid_style_custom_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(TicketStates.pack_style_custom)
    await callback.message.edit_text(
        "✏️ <b>Опиши свой стиль</b>\n\n"
        "Напиши подробное описание желаемого вида пака.\n\n"
        "<i>Например: синие тона, аниме-стиль, с золотыми деталями</i>",
        reply_markup=cancel_kb()
    )
    await callback.answer()

@dp.message(TicketStates.pack_style_custom)
async def paid_style_custom_done(message: Message, state: FSMContext):
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
    ok = await send_ticket_to_admin(user, ticket, is_free=False)
    if ok:
        await message.answer(
            "✅ <b>Заявка отправлена!</b>\n\n"
            f"📦 Пак: <b>{ticket['name']}</b>\n"
            f"🎨 Стиль: {ticket['style']}\n\n"
            "Администратор получил твой тикет и скоро приступит к работе. "
            "Как только пак будет готов — ты получишь ссылку прямо здесь! 🚀",
            reply_markup=back_to_menu_kb()
        )
    else:
        await message.answer(
            "⚠️ Не удалось отправить тикет. Попробуй позже.",
            reply_markup=back_to_menu_kb()
        )

# ─── Cancel (paid) ───────────────────────────────────────────────────────────

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
async def cb_free_pack(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if user_id in free_pack_used:
        await callback.message.edit_text(
            "❌ <b>Бесплатный пак уже получен.</b>\n\n"
            "Бесплатная попытка доступна только один раз. "
            "Чтобы заказать ещё — воспользуйся кнопкой <b>«Сделать пак»</b>.",
            reply_markup=back_to_menu_kb()
        )
        await callback.answer()
        return

    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await callback.message.edit_text(
            "🎁 <b>Получи эмодзи пак бесплатно!</b>\n\n"
            "Для этого нужно подписаться на наш канал.\n\n"
            "1️⃣ Нажми <b>«Подписаться на канал»</b>\n"
            "2️⃣ Подпишись\n"
            "3️⃣ Нажми <b>«Я подписался»</b> для проверки",
            reply_markup=check_sub_kb()
        )
        await callback.answer()
        return

    await state.set_state(FreeTicketStates.pack_name)
    await callback.message.edit_text(
        "🎁 <b>Отлично! Подписка подтверждена.</b>\n\n"
        "Оформим твой бесплатный пак!\n\n"
        "📦 <b>Шаг 1 из 4 — Название пака</b>\n\n"
        "Введи желаемое название для твоего эмодзи пака:\n\n"
        "<i>Например: MyPackName или CoolEmojis</i>",
        reply_markup=cancel_free_kb()
    )
    await callback.answer()

@dp.callback_query(F.data == "check_sub")
async def cb_check_sub(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    if user_id in free_pack_used:
        await callback.message.edit_text(
            "❌ <b>Бесплатный пак уже получен.</b>\n\n"
            "Бесплатная попытка доступна только один раз.",
            reply_markup=back_to_menu_kb()
        )
        await callback.answer()
        return

    is_subscribed = await check_subscription(user_id)
    if not is_subscribed:
        await callback.answer("❌ Ты ещё не подписан на канал!", show_alert=True)
        return

    await state.set_state(FreeTicketStates.pack_name)
    await callback.message.edit_text(
        "🎁 <b>Отлично! Подписка подтверждена.</b>\n\n"
        "Оформим твой бесплатный пак!\n\n"
        "📦 <b>Шаг 1 из 4 — Название пака</b>\n\n"
        "Введи желаемое название для твоего эмодзи пака:\n\n"
        "<i>Например: MyPackName или CoolEmojis</i>",
        reply_markup=cancel_free_kb()
    )
    await callback.answer("✅ Подписка подтверждена!")

# ─── Free Ticket Steps ───────────────────────────────────────────────────────

@dp.message(FreeTicketStates.pack_name)
async def free_step_name(message: Message, state: FSMContext):
    await state.update_data(pack_name=message.text.strip())
    await state.set_state(FreeTicketStates.pack_link)
    await message.answer(
        "🔗 <b>Шаг 2 из 4 — Ссылка на пак</b>\n\n"
        "Отправь ссылку на существующий пак или укажи желаемый адрес:\n\n"
        "<i>Например: t.me/addemoji/packname</i>",
        reply_markup=cancel_free_kb()
    )

@dp.message(FreeTicketStates.pack_link)
async def free_step_link(message: Message, state: FSMContext):
    await state.update_data(pack_link=message.text.strip())
    await state.set_state(FreeTicketStates.pack_nick)
    await message.answer(
        "✏️ <b>Шаг 3 из 4 — Ник на эмодзи</b>\n\n"
        "Введи ник или надпись, которая будет на эмодзи:",
        reply_markup=cancel_free_kb()
    )

@dp.message(FreeTicketStates.pack_nick)
async def free_step_nick(message: Message, state: FSMContext):
    await state.update_data(pack_nick=message.text.strip())
    await state.set_state(FreeTicketStates.pack_style)
    await message.answer(
        "🎨 <b>Шаг 4 из 4 — Вид пака</b>\n\n"
        "Выбери стиль оформления эмодзи пака:",
        reply_markup=style_kb(free=True)
    )

@dp.callback_query(FreeTicketStates.pack_style, F.data == "free_style_standard")
async def free_style_standard(callback: CallbackQuery, state: FSMContext):
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
    free_pack_used.add(callback.from_user.id)
    ok = await send_ticket_to_admin(user, ticket, is_free=True)
    if ok:
        await callback.message.edit_text(
            "🎁 <b>Бесплатная заявка отправлена!</b>\n\n"
            f"📦 Пак: <b>{ticket['name']}</b>\n"
            f"🎨 Стиль: {ticket['style']}\n\n"
            "Администратор получил твой тикет. "
            "Как только пак будет готов — ты получишь ссылку прямо здесь! 🚀",
            reply_markup=back_to_menu_kb()
        )
    else:
        free_pack_used.discard(callback.from_user.id)
        await callback.message.edit_text(
            "⚠️ Не удалось отправить тикет. Попробуй позже.",
            reply_markup=back_to_menu_kb()
        )
    await callback.answer()

@dp.callback_query(FreeTicketStates.pack_style, F.data == "free_style_custom")
async def free_style_custom_prompt(callback: CallbackQuery, state: FSMContext):
    await state.set_state(FreeTicketStates.pack_style_custom)
    await callback.message.edit_text(
        "✏️ <b>Опиши свой стиль</b>\n\n"
        "Напиши подробное описание желаемого вида пака.\n\n"
        "<i>Например: синие тона, аниме-стиль, с золотыми деталями</i>",
        reply_markup=cancel_free_kb()
    )
    await callback.answer()

@dp.message(FreeTicketStates.pack_style_custom)
async def free_style_custom_done(message: Message, state: FSMContext):
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
    free_pack_used.add(message.from_user.id)
    ok = await send_ticket_to_admin(user, ticket, is_free=True)
    if ok:
        await message.answer(
            "🎁 <b>Бесплатная заявка отправлена!</b>\n\n"
            f"📦 Пак: <b>{ticket['name']}</b>\n"
            f"🎨 Стиль: {ticket['style']}\n\n"
            "Администратор получил твой тикет. "
            "Как только пак будет готов — ты получишь ссылку прямо здесь! 🚀",
            reply_markup=back_to_menu_kb()
        )
    else:
        free_pack_used.discard(message.from_user.id)
        await message.answer(
            "⚠️ Не удалось отправить тикет. Попробуй позже.",
            reply_markup=back_to_menu_kb()
        )

# ─── Cancel (free) ───────────────────────────────────────────────────────────

@dp.callback_query(F.data == "cancel_free_ticket")
async def cb_cancel_free(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        "❌ <b>Заявка отменена.</b>\n\nВозвращаемся в главное меню:",
        reply_markup=main_menu_kb()
    )
    await callback.answer("Отменено")

# ─── Admin reply → forward to user ───────────────────────────────────────────

@dp.message(F.reply_to_message)
async def handle_admin_reply(message: Message):
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
