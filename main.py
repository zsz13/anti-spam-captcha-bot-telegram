import asyncio
from datetime import time, datetime
import os.path
import re
import random
import logging
import pandas as pd

from aiogram import types, Bot, Dispatcher, executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import StatesGroup, State
from aiogram.types import ChatPermissions

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from config import API_TOKEN, SPREADSHEET_ID, CHAT_ID


storage = MemoryStorage()
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=storage)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
CAPTCHA_IMAGES_PATH = "captcha_images"
log_directory = 'logs'
os.makedirs(log_directory, exist_ok=True)
log_file = os.path.join(log_directory, f'bot_log_{datetime.now().strftime("%Y-%m-%d_%H-%M-%S")}.txt')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler = logging.FileHandler(log_file)
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(formatter)
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(file_handler)


async def on_startup(_):
    try:
        logging.info('Bot started')
        # print('Вход в def on_startup try')
        sheets_api = await initialize_sheets_api()
        await get_sheet_values(sheets_api.spreadsheets(), SPREADSHEET_ID, "A1:A989")
        await main()
    except Exception as e:
        # print(f'exception in def on_startup is - {e}')
        logging.error(f'exception in def on_startup is - {e}')


async def update_data_periodically():
    while True:
        await asyncio.sleep(86400)
        sheets_api = await initialize_sheets_api()
        await get_sheet_values(sheets_api.spreadsheets(), SPREADSHEET_ID, "A1:A989")
        # print("The data from google sheets has been successfully updated")
        logging.info('The data from google sheets has been successfully updated')


async def main():
    asyncio.create_task(update_data_periodically())
    logging.info('asyncio created task update_data_periodically()')
    # print('asyncio created task update_data_periodically()')
    asyncio.create_task(update_cell_data_ban_mode_periodically())
    logging.info('asyncio created task update_cell_data_ban_mode_periodically()')
    # print('asyncio created task update_cell_data_ban_mode_periodically()')


async def initialize_sheets_api():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("sheets", "v4", credentials=creds)


async def get_sheet_values(sheet_api, spreadsheet_id, range):
    result = sheet_api.values().get(spreadsheetId=spreadsheet_id, range=range).execute()
    # print(f'Data from google sheets: {result}')
    values = result.get("values", [])
    logging.info(f'Data from google sheets forbidden words: {result}')
    df = pd.DataFrame(values[1:], columns=values[0])
    df.to_csv("data.csv", index=False)
    logging.info('The data has been converted to csv format in a file "data.csv"')
    return values


async def get_cell_data_ban_mode(sheet_api, spreadsheet_id, range):
    # print('Вход в def get_cell_data_ban_mode')
    result = sheet_api.values().get(spreadsheetId=spreadsheet_id, range=range).execute()
    values = result.get("values", [])
    if values:
        with open("cell_data_ban_mode.txt", "w") as file:
            for row in values:
                file.write(row[0])
    else:
        # print("No data in the specified cell.")
        logging.warning('No data in the specified cell.')


async def update_cell_data_ban_mode_periodically():
    while True:
        # print('Вход в def update_cell_data_ban_mode_periodically')
        await asyncio.sleep(3600)
        sheets_api = await initialize_sheets_api()
        await get_cell_data_ban_mode(sheets_api.spreadsheets(), SPREADSHEET_ID, "Список стоп слов!C2")
        # print("Cell data ban mode has been successfully updated")
        logging.info("Cell data ban mode has been successfully updated")


class CaptchaStates(StatesGroup):
    waiting_for_captcha = State()
    captcha_check_failed = State()
    captcha_check_passed = State()

    async def on_enter_waiting_for_captcha(self, message: types.Message, state: FSMContext):
        data = await state.get_data()
        if "start_time" not in data or not data.get("waiting_started"):
            await state.update_data(start_time=datetime.now(), waiting_started=True)


async def timer_callback(chat_id, state: FSMContext, user_id, message):
    try:
        curr_state = await state.get_state()
        # print(f'Current state до asyncio.sleep в def timer_callback try - {curr_state}')
        logging.info(f'Current state before asyncio.sleep in def timer_callback try - {curr_state}')
        # print('Вход в def timer_callback try блок ')
        await asyncio.sleep(60)
        current_state = await state.get_state()
        # print(f'Current state after 60 sec asyncio.sleep in timer callback try - {current_state}')
        logging.info(f'Current state after 60 sec asyncio.sleep in timer callback try - {current_state}')
        data_state = await state.get_data()
        # print(f'Data state after 60 sec asyncio.sleep in timer callback try - {data_state}')
        logging.info(f'Data state after 60 sec asyncio.sleep in timer callback try - {data_state}')
        if current_state == CaptchaStates.waiting_for_captcha.state:
            # print('Вход в if внутри def timer_callback')
            await CaptchaStates.captcha_check_failed.set()
            currentttt_state1 = await state.get_state()
            # print(f"Current State внутри def timer_callback if: {currentttt_state1}")
            logging.info(f"Current State inside def timer_callback if: {currentttt_state1}")
            message_to_user_timer_ended = await bot.send_message(chat_id, "Время на подтверждение вышло, вы не прошли "
                                                                          "проверку капчи и будете заблокированы.")
            logging.info('Bot send message - "Время на подтверждение вышло, вы не прошли проверку капчи и будете'
                         ' заблокированы."')
            await bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
            logging.info(f'A user has been blacklisted - {message.from_user.id}')
            await bot.kick_chat_member(chat_id=CHAT_ID, user_id=user_id)
            logging.info(f'A user has been kicked - {message.from_user.id}')
            await asyncio.sleep(60)
            await bot.delete_message(chat_id, message_to_user_timer_ended.message_id)
            next_message_sent_from_bot = (
                        "Таймер закончился. Вы не прошли проверку капчи."
                    )
            # print(f'Заблокирован пользователь с id - {user_id}')
            # print(f'Next message sent bot in the chat is - {next_message_sent_from_bot}')
            logging.info(f'Next message sent bot in the chat is - {next_message_sent_from_bot}')
        else:
            pass
            # print('Вход в else')
    except Exception as e:
        logging.error(f'An error occurred in def timer_callback - {e}')
        # print('exception сработал - ' + str(e))
    finally:
        # print('Вход в def timer_callback - finally ')
        await state.finish()
        logging.info('def timer callback finished')
        # current_state = await state.get_state()
        # print(f"Current State внутри def timer_callback - finally: {current_state}")


async def get_captcha_text(image_filename):
    # print('Вход в def get_captcha_text')
    logging.info('Entering the def get_captcha_text')
    switch = {
        "bArnaul8.jpg": ["бАрнаул8", "bArnaul8"],
        "bArsik38.jpg": ["бАрсик38", "bArsik38"],
        "Berkut+.jpg": ["Беркут+", "Berkut+"],
        "GAGARIN.jpg": ["ГАГАРИН", "GAGARIN"],
        "GORA_BELUHA.jpg": ["ГОРА БЕЛУХА", "GORA BELUHA"],
        "PETROPAVLOVSK.jpg": ["ПЕТРОПАВЛОВСК", "PETROPAVLOVSK"],
        "RAKETA.jpg": ["РАКЕТА", "RAKETA"],
        "TORPEDO.jpg": ["ТОРПЕДО", "TORPEDO"],
    }
    return switch.get(image_filename, ["default_text"])


@dp.message_handler(content_types=types.ContentType.TEXT)
async def handle_text(message: types.Message, state: FSMContext):
    logging.info(f'User info: {message.from_user}')
    logging.info(f'Received message: {message.text}')
    await main()
    with open("cell_data_ban_mode.txt", "r") as file:
        ban_mode = file.read().strip()
        # print(f'ban_mode is - {ban_mode}')
        logging.info(f'Ban mode is - {ban_mode}')
    values = pd.read_csv("data.csv").values.tolist()
    if not values:
        # print("No data in table.")
        logging.warning("No data in table.")
    else:
        current_state = await state.get_state()
        logging.info(f"Current State in def handle_text else - {current_state}")
        # print(f"Current State внутри def handle_text - else: {current_state}")
        forbidden_words = [word for row in values for word in row]
        logging.info(f"Forbidden words: {forbidden_words}")
        # print("Message from user in chat: " + message.text)
        if ban_mode == "с каптчей":
            # print('Вход в if ban_mode == "с каптчей"')
            for word in message.text.split():
                if word.lower() in map(str.lower, forbidden_words) or re.search(
                        r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+|\b\w+\.\w+\b',
                        message.text.lower()) or re.search(r'@\w+', message.text):
                    captcha_images = [img for img in os.listdir(CAPTCHA_IMAGES_PATH) if img.endswith(".jpg")]
                    selected_image = random.choice(captcha_images)
                    logging.info(f"Selected image: {selected_image}")
                    # print(f'Random selected image is - {selected_image}')
                    captcha_image_path = os.path.join(CAPTCHA_IMAGES_PATH, selected_image)
                    possible_captcha_texts = await get_captcha_text(selected_image)
                    await state.update_data(possible_captcha_texts=possible_captcha_texts)
                    with open(captcha_image_path, "rb") as captcha_image:
                        first_message_from_bot = (
                            f"В вашем сообщении есть запретное слово: {word}."
                            " Подтвердите, что вы не бот в течение"
                            " 60 секунд, иначе будете удалены. Введите текст с картинки на русском языке соблюдая "
                            "регистр."
                        )
                        logging.info(f"First message sent bot in the chat: {first_message_from_bot}")
                        # print(f'First message sent bot in the chat is - {first_message_from_bot}')
                        message_to_user_send_photo = await message.reply_photo(captcha_image,
                                                                               caption="В вашем сообщении есть "
                                                                                       "запретное"
                                                                                       f' слово: "{word}". \n\n'
                                                                                       "Отправьте проверочное слово в "
                                                                                       "чат, в течение 60 секунд, иначе"
                                                                                       " будете удалены. \n\n"
                                                                                       "Введите текст с картинки на "
                                                                                       "кириллице или латинице соблюдая"
                                                                                       " регистр.")
                        await CaptchaStates.waiting_for_captcha.set()
                        await state.update_data(start_time=datetime.now(), waiting_started=True)
                        current_state1 = await state.get_state()
                        logging.info("Current State inside def handle_text else if word in forbidden_words -"
                                     f" {current_state1}")
                        # print(
                        #     f"Current State внутри def handle_text else - if word in forbidden_words: {current_state1}")
                        # print('Message from user - ' + str(message.from_user))
                        user_id = message.from_user.id
                        asyncio.create_task(timer_callback(message.chat.id, state, user_id, message))
                        logging.info('asyncio created task timer_callback(message.chat.id, state, user_id)')
                        await asyncio.sleep(60)
                        await bot.delete_message(chat_id=CHAT_ID, message_id=message.message_id)
                        await bot.delete_message(chat_id=CHAT_ID, message_id=message_to_user_send_photo.message_id)
                        break

        elif ban_mode == "моментальный":
            logging.info('Ban mode is - "моментальный"')
            # print('Вход в elif ban_mode == "моментальный":')
            for word in message.text.split():
                if word.lower() in map(str.lower, forbidden_words):
                    try:
                        logging.info(f'Message from user is - {message.from_user}')
                        user_id = message.from_user.id
                        await bot.delete_message(chat_id=CHAT_ID, message_id=message.message_id)
                        await bot.ban_chat_member(chat_id=CHAT_ID, user_id=user_id)
                        logging.info(f'A user has been blacklisted - {message.from_user.id}')
                        await bot.kick_chat_member(chat_id=CHAT_ID, user_id=user_id)
                        logging.info(f'A user has been kicked - {message.from_user.id}')
                        # print(f'Удален и внесен в черный список пользователь с id - {user_id}')
                        # next_message_sent_from_bot = await message.answer(
                        #     "Вы будете заблокированы так как в вашем сообщении было запрещенное слово"
                        # )
                        # print(f'Message is -{message}')
                        # await bot.send_message(CHAT_ID, next_message_sent_from_bot)
                        # await asyncio.sleep(60)
                        # await bot.delete_message(chat_id=CHAT_ID, message_id=next_message_sent_from_bot.message_id)
                        break
                    except Exception as e:
                        logging.error(f"An error occurred while trying to restrict chat member: {e}")
                        # print(f"An error occurred while trying to restrict chat member: {e}")
                        break


@dp.message_handler(content_types=[
    types.ContentType.NEW_CHAT_MEMBERS,
    types.ContentType.LEFT_CHAT_MEMBER,
    types.ContentType.NEW_CHAT_TITLE,
    types.ContentType.NEW_CHAT_PHOTO,
    types.ContentType.DELETE_CHAT_PHOTO
])
async def delete_system_messages(message: types.Message):
    # print('ВХОД В handler системных сообщений def delete_system_messages')
    await bot.delete_message(CHAT_ID, message.message_id)


@dp.message_handler(state=CaptchaStates.waiting_for_captcha)
async def handle_captcha_waiting(message: types.Message, state: FSMContext):
    data = await state.get_data()
    logging.info(f"State's data inside def handle_captcha_waiting is - {data}")
    # print(f"State's data inside def handle_captcha_waiting is - {data}")
    current_time = datetime.now()
    start_time = data.get("start_time", current_time)
    # print(f'Start time is - {start_time}')
    elapsed_time = int((current_time - start_time).total_seconds())
    # print(f'Elapsed time is - {elapsed_time} seconds')
    # print(f'Current time is - {current_time}')
    possible_captcha_texts = data.get("possible_captcha_texts")
    cs = await state.get_state()
    if elapsed_time >= 60:
        try:
            await bot.send_message(chat_id=CHAT_ID,
                                   text=(f"Время ожидания истекло. Вы будете удалены за неудачную проверку капчи. "
                                         f"Время вашего ответа - {elapsed_time}"))
            next_message_sent_from_bot = (f'Время ожидания истекло. Вы будете удалены за неудачную проверку капчи.'
                                          f"Время вашего ответа - {elapsed_time}")
            logging.info(f'Next message sent bot in the chat is - {next_message_sent_from_bot}')
            # print(f'Next message sent bot in the chat is - {next_message_sent_from_bot}')
            await CaptchaStates.captcha_check_failed.set()
            current_state1 = await state.get_state()
            # print(f"Current State внутри def handle_captcha_waiting: {current_state1}")
        except Exception as e:
            logging.error(f"An error occurred in def handle_captcha_waiting if - {e}")
            # print(f"An error occurred - {e}")
    else:
        if message.text in possible_captcha_texts:
            # print("Сообщение от пользователя в чате: " + message.text)
            message_to_user_send_captcha_passed = await message.reply('Спасибо! Вы успешно прошли проверку. Время '
                                                                      f'вашего ответа - {elapsed_time} секунд(-ы)')
            next_message_sent_from_bot1 = (f'Спасибо! Вы успешно прошли проверку. Время вашего ответа'
                                           f' - {elapsed_time} секунд(-ы)')
            logging.info(f'Next message sent bot in the chat is - {next_message_sent_from_bot1}')
            # print(f'Next message sent bot in the chat is - {next_message_sent_from_bot1}')
            await CaptchaStates.captcha_check_passed.set()
            current_state2 = await state.get_state()
            await state.update_data(waiting_started=False)
            logging.info(f"Current State inside def handle_captcha_waiting else if - {current_state2}")
            # print(f"Current State внутри def handle_captcha_waiting else - if - {current_state2}")
            await asyncio.sleep(60)
            await bot.delete_message(chat_id=CHAT_ID, message_id=message_to_user_send_captcha_passed.message_id)
            await bot.delete_message(chat_id=CHAT_ID, message_id=message.message_id)
        elif message.text not in possible_captcha_texts and cs != CaptchaStates.captcha_check_failed.state:
            # print("Message from user in chat: " + message.text)
            current_state3 = await state.get_state()
            logging.info(f"Current State inside def handle_captcha_waiting else elif - {current_state3}")
            # print(f"Current State внутри def handle_captcha_waiting else elif - {current_state3}")
            next_message_from_bot = f'Неверный текст. Пожалуйста, введите текст с картинки. ' \
                                    f'Прошло секунд - {elapsed_time}'
            logging.info(f'Next message sent bot in the chat is - {next_message_from_bot}')
            # print(f'Next message sent bot in the chat is - {next_message_from_bot}')
            message_to_user_send_photo_again = await message.reply('Неверный текст. Пожалуйста, введите текст с '
                                                                   f'картинки. Прошло секунд - {elapsed_time}')
            await asyncio.sleep(60)
            await bot.delete_message(chat_id=CHAT_ID, message_id=message_to_user_send_photo_again.message_id)
        else:
            pass
            # print('Вход в def handle_captcha_waiting else else')


@dp.message_handler(state=CaptchaStates.captcha_check_passed, content_types=types.ContentType.TEXT)
async def handle_captcha_passed(message: types.Message, state: FSMContext):
    logging.info('Enter inside @dp.message_handler(state=CaptchaStates.captcha_check_passed - def handle_captcha_passed')
    # print('Вход в @dp.message_handler(state=CaptchaStates.captcha_check_passed - def handle_captcha_passed')
    await state.finish()


@dp.message_handler(state=CaptchaStates.captcha_check_failed, content_types=types.ContentType.TEXT)
async def handle_captcha_failed(message: types.Message, state: FSMContext):
    logging.info('Enter inside @dp.message_handler(state=CaptchaStates.captcha_check_failed - def handle_captcha_failed')
    # print('Вход в @dp.message_handler(state=CaptchaStates.captcha_check_failed - def handle_captcha_failed')
    await state.finish()


if __name__ == '__main__':
    logging.info('Bot script executed')
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)





