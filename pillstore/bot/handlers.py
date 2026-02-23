import logging
import re

import aiohttp
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    WebAppInfo,
)
from api_client import client
from config import API_BASE_URL, MINI_APP_PUBLIC_URL, SITE_URL

logger = logging.getLogger(__name__)
router = Router()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

REGISTER_HERE_CB = "register_here"


class AuthStates(StatesGroup):
    wait_password = State()

MINI_APP_URL = f"{API_BASE_URL}/mini"
MINI_APP_LINK_URL = f"{MINI_APP_PUBLIC_URL}/mini"


def _shop_keyboard() -> ReplyKeyboardMarkup | InlineKeyboardMarkup:
    if MINI_APP_PUBLIC_URL.startswith("https://"):
        return InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🛒 Открыть магазин",
                        web_app=WebAppInfo(url=MINI_APP_LINK_URL),
                    )
                ]
            ]
        )
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛒 Открыть магазин (в браузере)")],
        ],
        resize_keyboard=True,
    )


@router.message(F.text == "/start")
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    try:
        if await client.is_telegram_linked(message.from_user.id):
            text = (
                "Вы уже привязаны к аккаунту. "
                "Нажмите кнопку ниже, чтобы открыть магазин."
            )
            kb = _shop_keyboard()
            if isinstance(kb, InlineKeyboardMarkup):
                await message.answer(text, reply_markup=kb)
            else:
                await message.answer(text, reply_markup=kb)
            return
    except Exception:
        pass
    await message.answer(
        "Добро пожаловать в PillStore.\n\n"
        "Введите ваш email - проверю, зарегистрирован ли он на сайте, "
        "и привяжу бота к вашему аккаунту. После этого откроется мини-приложение магазина "
    )


@router.message(F.text == "/help")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "Помощь:\n"
        "/start - приветствие и привязка по email\n"
        "После привязки нажмите «Открыть магазин» - откроется мини-приложение с каталогом, "
        "корзиной и оформлением заказа (с подтверждением политики конфиденциальности)."
    )


def _keyboard_register_choices(email: str) -> InlineKeyboardMarkup:
    site_register_url = f"{SITE_URL}/auth/register"
    buttons = []
    if site_register_url.startswith("https://") and "localhost" not in site_register_url:
        buttons.append([InlineKeyboardButton(text="🌐 Перейти на сайт", url=site_register_url)])
    buttons.append([InlineKeyboardButton(text="📱 Зарегистрироваться в боте", callback_data=REGISTER_HERE_CB)])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@router.message(F.text.regexp(EMAIL_RE))
async def on_email(message: Message, state: FSMContext) -> None:
    email = (message.text or "").strip()
    await state.clear()
    try:
        exists = await client.check_email_exists(email)
        if not exists:
            text = (
                "Пользователь с таким email не найден.\n\n"
                "Вы можете зарегистрироваться на сайте или здесь, в боте (email + пароль)."
            )
            site_url = f"{SITE_URL}/auth/register"
            if not (site_url.startswith("https://") and "localhost" not in site_url):
                text += f"\n\nСайт: {site_url}"
            await message.answer(text, reply_markup=_keyboard_register_choices(email))
            await state.update_data(pending_email=email)
            return
        ok, err = await client.link_telegram(email, message.from_user.id)
        if not ok:
            await message.answer(err or "Ошибка привязки. Попробуйте позже.")
            return
        text = (
            "Email найден, аккаунт привязан. "
            "Нажмите кнопку ниже, чтобы открыть магазин."
        )
        kb = _shop_keyboard()
        if isinstance(kb, InlineKeyboardMarkup):
            await message.answer(text, reply_markup=kb)
        else:
            await message.answer(text, reply_markup=kb)
    except aiohttp.ClientError as e:
        logger.warning("API недоступен при проверке email: %s", e)
        await message.answer(
            "Сервер магазина недоступен. Попробуйте позже."
        )
    except Exception as e:
        logger.exception("Ошибка при обработке email: %s", e)
        await message.answer("Ошибка связи с сервером. Попробуйте позже.")


@router.callback_query(F.data == REGISTER_HERE_CB)
async def on_register_here(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    email = data.get("pending_email", "").strip()
    await callback.answer()
    if not email:
        await callback.message.answer("Сессия сброшена. Отправьте /start и снова введите email.")
        await state.clear()
        return
    await state.set_state(AuthStates.wait_password)
    await callback.message.answer(
        "Введите пароль для регистрации (минимум 8 символов):"
    )


@router.message(AuthStates.wait_password, F.text)
async def on_password_register(message: Message, state: FSMContext) -> None:
    password = (message.text or "").strip()
    data = await state.get_data()
    email = data.get("pending_email", "").strip()
    await state.clear()
    if not email:
        await message.answer("Сессия сброшена. Отправьте /start и введите email.")
        return
    try:
        user, reg_error = await client.register(email, password, role="buyer")
        if user is None:
            await message.answer(reg_error or "Не удалось зарегистрироваться. Попробуйте снова или зарегистрируйтесь на сайте.")
            return
        ok, link_error = await client.link_telegram(email, message.from_user.id)
        if not ok:
            await message.answer(link_error or "Аккаунт создан, но привязка не удалась. Напишите /start и введите email снова.")
            return
        token, _ = await client.get_mini_app_token(message.from_user.id)
        text = ("Вы зарегистрированы и привязаны к аккаунту. ")
        if token:
            link = f"{MINI_APP_LINK_URL}?t={token}"
            text += f'Откройте магазин: <a href="{link}">🛒 Приложение PillStore</a>'
        else:
            text += "Нажмите кнопку ниже, чтобы открыть магазин."
        await message.answer(text, reply_markup=_shop_keyboard(), parse_mode="HTML")
    except aiohttp.ClientError as e:
        logger.warning("API недоступен при регистрации: %s", e)
        await message.answer(
            "Сервер магазина недоступен. Попробуйте позже."
        )
    except Exception as e:
        logger.exception("Ошибка при регистрации: %s", e)
        await message.answer("Ошибка связи с сервером. Попробуйте позже.")


@router.message(F.text == "🛒 Открыть магазин (в браузере)")
async def open_shop_browser(message: Message) -> None:
    token, err = await client.get_mini_app_token(message.from_user.id)
    if not token:
        await message.answer(err or "Не удалось получить ссылку. Привяжите аккаунт: /start и введите email.")
        return
    link = f"{MINI_APP_LINK_URL}?t={token}"
    await message.answer(f'<a href="{link}">🛒 Открыть магазин PillStore</a>')


@router.message(F.text)
async def on_other(message: Message, state: FSMContext) -> None:
    if await state.get_state() == AuthStates.wait_password:
        await message.answer("Введите пароль (минимум 8 символов) или /start для отмены.")
        return
    await message.answer(
        "Введите корректный email для привязки аккаунта (после /start)."
    )
