import asyncio
import logging
import time

import requests
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (Message, CallbackQuery, WebAppInfo, MenuButtonWebApp,
                           InlineKeyboardMarkup, InlineKeyboardButton)

from app import config as C
from app import db, subgen, provisioner

log = logging.getLogger("vpnbanana.bot")
env = C.load_env()
WEBAPP_URL = f"https://{C.DOMAIN}/app"
ADMIN_URL = f"https://{C.DOMAIN}/admin"
SUPPORT = C.SUPPORT_URL or "администратору"
bot = None
dp = Dispatcher()
CONN = db.connect(env["DB_PATH"]); db.init_schema(CONN)
ADMIN = env["ADMIN_ID"]

GB = 1024 ** 3

WIZ = {}


def kb(rows):
    return InlineKeyboardMarkup(inline_keyboard=rows)


def online_map():
    try:
        r = requests.get(f"{env['HY_MAIN_STATS']}/online",
                         headers={"Authorization": env["HYSTERIA_STATS_SECRET"]}, timeout=3)
        r.raise_for_status()
        return r.json()
    except Exception:
        log.warning("hysteria /online unavailable", exc_info=True)
        return {}


@dp.message(CommandStart())
async def start(m: Message):
    if m.from_user.id == ADMIN:
        await m.answer("Админ-панель. /users - список подписок, /stats - расход.")
        return

    if db.get_user_by_tg(CONN, m.from_user.id):
        await m.answer(
            "У тебя уже есть подписка BananaVPN. Всё управление - в личном кабинете: "
            "трафик, устройства, подключение.",
            reply_markup=kb([[InlineKeyboardButton(text="🔐 Открыть кабинет", web_app=WebAppInfo(url=WEBAPP_URL))]]))
        return
    await m.answer(f"Чтобы получить подписку {C.PROFILE_TITLE}, напиши {SUPPORT}.")
    uname = ("@" + m.from_user.username) if m.from_user.username else m.from_user.full_name
    await bot.send_message(
        ADMIN, f"Пользователь {uname} (id {m.from_user.id}) зашел в бота.",
        reply_markup=kb([[InlineKeyboardButton(
            text="Выдать подписку",
            callback_data=f"iss:{m.from_user.id}:{m.from_user.username or '-'}")]]))


@dp.callback_query(F.data.startswith("iss:"))
async def issue_start(cq: CallbackQuery):
    _, tg, uname = cq.data.split(":", 2)
    WIZ[cq.message.message_id] = {"tg": int(tg), "username": uname,
                                  "traffic": None, "torrent": None, "dev": None}
    await cq.message.edit_text(
        f"Выдача для id {tg}. Трафик:",
        reply_markup=kb([[InlineKeyboardButton(text="100 ГБ", callback_data="t:100"),
                          InlineKeyboardButton(text="300 ГБ", callback_data="t:300"),
                          InlineKeyboardButton(text="Безлимит", callback_data="t:0")]]))
    await cq.answer()


@dp.callback_query(F.data.startswith("t:"))
async def pick_traffic(cq: CallbackQuery):
    w = WIZ.get(cq.message.message_id)
    if not w:
        return await cq.answer("Сессия истекла", show_alert=True)
    w["traffic"] = int(cq.data.split(":")[1])
    await cq.message.edit_text(
        "Торренты:",
        reply_markup=kb([[InlineKeyboardButton(text="Резать", callback_data="tor:1"),
                          InlineKeyboardButton(text="Разрешить", callback_data="tor:0")]]))
    await cq.answer()


@dp.callback_query(F.data.startswith("tor:"))
async def pick_torrent(cq: CallbackQuery):
    w = WIZ.get(cq.message.message_id)
    if not w:
        return await cq.answer("Сессия истекла", show_alert=True)
    w["torrent"] = int(cq.data.split(":")[1])
    await cq.message.edit_text(
        "Устройств:",
        reply_markup=kb([[InlineKeyboardButton(text=str(n), callback_data=f"d:{n}")
                          for n in (1, 2, 3, 5)]]))
    await cq.answer()


@dp.callback_query(F.data.startswith("d:"))
async def pick_dev(cq: CallbackQuery):
    w = WIZ.get(cq.message.message_id)
    if not w:
        return await cq.answer("Сессия истекла", show_alert=True)
    w["dev"] = int(cq.data.split(":")[1])
    limit = None if w["traffic"] == 0 else w["traffic"] * GB
    try:
        token = await asyncio.to_thread(provisioner.new_user, CONN, env, tg_id=w["tg"],
                                        username=w["username"], traffic_limit_bytes=limit,
                                        device_limit=w["dev"], torrent_block=w["torrent"])
    except Exception as e:
        WIZ.pop(cq.message.message_id, None)
        await cq.message.edit_text(f"Ошибка выдачи (Xray не перестроился): {e}. Попробуй еще раз.")
        return await cq.answer("Ошибка", show_alert=True)
    crypt_ok = True
    try:
        link = await asyncio.to_thread(subgen.crypt5_link, subgen.sub_url(token))
        db.set_crypt5(CONN, token, link)
    except Exception:
        crypt_ok = False
    landing = subgen.landing_url(token)
    msg = f"Выдано. Кабинет/подключение: {landing}"
    if not crypt_ok:
        msg += "\n⚠ crypt5 не сгенерился (Happ-сервис недоступен) - кнопка 'Подключить' соберется при открытии лендинга."
    await cq.message.edit_text(msg)
    try:
        await bot.send_message(
            w["tg"],
            "Твоя подписка BananaVPN готова. Открой кабинет (кнопка ниже или меню), там подключение и управление устройствами:",
            reply_markup=kb([[InlineKeyboardButton(text="🔐 Открыть кабинет", web_app=WebAppInfo(url=WEBAPP_URL))],
                             [InlineKeyboardButton(text="📥 Установить Happ", url="https://happ.info"),
                              InlineKeyboardButton(text="Подключение", url=landing)]]))
    except Exception:
        await cq.message.answer("Не смог написать юзеру напрямую - перешли ссылку вручную: " + landing)
    WIZ.pop(cq.message.message_id, None)
    await cq.answer()


@dp.message(Command("users"))
async def users(m: Message):
    if m.from_user.id != ADMIN:
        return
    rows = db.all_users(CONN)
    if not rows:
        return await m.answer("Подписок нет.")
    now = int(time.time())
    online = await asyncio.to_thread(online_map)
    for u in rows[:30]:
        used = u["traffic_used_bytes"] / GB
        lim = "безлимит" if u["traffic_limit_bytes"] is None else f"{u['traffic_limit_bytes']/GB:.0f} ГБ"
        dev = db.device_count(CONN, u["token"])
        on = online.get(u["token"], 0)
        days = max(0, (u["expires_at"] - now) // 86400)
        txt = (f"@{u['username']} (id {u['tg_id']})\n"
               f"скачано: {used:.2f} ГБ / {lim} | онлайн: {on} | устройств: {dev}/{u['device_limit']}\n"
               f"осталось дней: {days} | статус: {u['status']}")
        await m.answer(txt, reply_markup=kb([[
            InlineKeyboardButton(text="+30 дней", callback_data=f"ext:{u['token']}"),
            InlineKeyboardButton(text="Отключить", callback_data=f"off:{u['token']}")]]))


@dp.message(Command("stats"))
async def stats(m: Message):
    if m.from_user.id != ADMIN:
        return
    active = [u for u in db.all_users(CONN) if u["status"] == "active"]
    if not active:
        return await m.answer("Активных подписок нет.")
    online = await asyncio.to_thread(online_map)
    active.sort(key=lambda u: u["traffic_used_bytes"], reverse=True)
    total = sum(u["traffic_used_bytes"] for u in active)
    lines = ["📊 Кто сколько скачал (по убыванию):", ""]
    for u in active[:40]:
        used = u["traffic_used_bytes"] / GB
        lim = "∞" if u["traffic_limit_bytes"] is None else f"{u['traffic_limit_bytes']/GB:.0f}ГБ"
        on = online.get(u["token"], 0)
        dev = db.device_count(CONN, u["token"])
        flag = " 🔴" if on else ""
        lines.append(f"@{u['username']}: {used:.2f}ГБ / {lim} · онлайн {on}{flag} · устройств {dev}/{u['device_limit']}")
    lines.append("")
    lines.append(f"Итого скачано всеми: {total / GB:.2f} ГБ | активных: {len(active)}")
    await m.answer("\n".join(lines))


@dp.callback_query(F.data.startswith("ext:"))
async def extend(cq: CallbackQuery):
    if cq.from_user.id != ADMIN:
        return await cq.answer()
    token = cq.data.split(":")[1]
    db.extend(CONN, token, 30)
    try:
        await asyncio.to_thread(provisioner.rebuild_xray, CONN, env)
    except Exception as e:
        return await cq.answer(f"Продлено в БД, но Xray не перестроился: {e}", show_alert=True)
    await cq.answer("Продлено на 30 дней", show_alert=True)


@dp.callback_query(F.data.startswith("off:"))
async def off(cq: CallbackQuery):
    if cq.from_user.id != ADMIN:
        return await cq.answer()
    token = cq.data.split(":")[1]
    db.set_status(CONN, token, "disabled")
    try:
        await asyncio.to_thread(provisioner.rebuild_xray, CONN, env)
    except Exception as e:
        return await cq.answer(f"Статус снят, но Xray не перестроился: {e}", show_alert=True)
    await asyncio.to_thread(provisioner.kick_hysteria, env, token)
    await cq.answer("Отключено", show_alert=True)


@dp.message(Command("cabinet"))
async def cabinet(m: Message):
    await m.answer(
        "Твой личный кабинет BananaVPN (трафик, устройства, подключение):",
        reply_markup=kb([[InlineKeyboardButton(text="🔐 Открыть кабинет", web_app=WebAppInfo(url=WEBAPP_URL))]]))


@dp.message(Command("admin"))
async def admin_cmd(m: Message):
    if m.from_user.id != ADMIN:
        return
    await m.answer(
        "Админка BananaVPN - все подписки, трафик, управление:",
        reply_markup=kb([[InlineKeyboardButton(text="🛠 Открыть админку",
                                               web_app=WebAppInfo(url=ADMIN_URL))]]))


async def main():
    global bot
    bot = Bot(env["BOT_TOKEN"])
    try:
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="Кабинет", web_app=WebAppInfo(url=WEBAPP_URL)))
    except Exception:
        log.warning("set_chat_menu_button failed", exc_info=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
