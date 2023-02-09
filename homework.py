import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv

load_dotenv()


PRACTICUM_TOKEN = os.getenv("PRACTICUM_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RETRY_PERIOD = 600
ENDPOINT = "https://practicum.yandex.ru/api/user_api/homework_statuses/"
HEADERS = {"Authorization": f"OAuth {PRACTICUM_TOKEN}"}


HOMEWORK_VERDICTS = {
    "approved": "Работа проверена: ревьюеру всё понравилось. Ура!",
    "reviewing": "Работа взята на проверку ревьюером.",
    "rejected": "Работа проверена: у ревьюера есть замечания.",
}

logging.basicConfig(
    level=logging.DEBUG,
    filename=os.path.join(os.path.dirname(__file__), "main.log"),
    format="%(asctime)s, %(levelname)s, %(message)s, %(name)s",
    encoding="utf--8",
)


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
logger.addHandler(handler)


def check_tokens():
    """Проверка доступности переменных окружения."""
    if not (PRACTICUM_TOKEN or TELEGRAM_TOKEN or TELEGRAM_CHAT_ID):
        logger.critical("Одна из требуемых переменных окружения отсутствует.")
        return False
    else:
        logger.info("Все требуемые переменные окружения доступны.")
        return True


def send_message(bot, message):
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, text=message)
        logger.debug("Сообщение о статусе отправлено.")
    except Exception as error:
        logger.error(f"Сбой при отправке сообщения в Telegram: {error}")


def get_api_answer(timestamp):
    """Запрос к эндпоинту API-сервиса."""
    cur_timestamp = timestamp or int(time.time())
    params = {"from_date": cur_timestamp}
    logger.info("Выполняется запрос к эндпоинту API-сервиса.")
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise Exception(f"Ошибка: {homework_statuses.status_code}.")
        return homework_statuses.json()
    except Exception:
        logger.error("Эндпоинт недоступен.")
        raise SystemError(
            f"Эндпоинт недоступен. Код ошибки {homework_statuses.status_code}"
        )


def check_response(response):
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError("Переменная не является словарем.")
    try:
        homeworks = response["homeworks"]
    except KeyError:
        logger.error("Ключ homeworks отсутствует.")
        raise KeyError("Ключ homeworks отсутствует.")
    if not isinstance(homeworks, list):
        raise TypeError("Список домашних работ не является типом list.")
    return homeworks


def parse_status(homework):
    """Извлечение информации о статусе домашней работы."""
    if "homework_name" not in homework:
        raise KeyError("Данная работа отсутствует в списке.")
    homework_name = homework.get("homework_name")
    homework_status = homework.get("status")
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f"Статуса {homework_status} не существует.")
    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{HOMEWORK_VERDICTS[homework_status]}'
    ).format(homework_name=homework_name)


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical("Недоступны переменные окружения.")
        sys.exit("Недоступны переменные окружения.")
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message = "Начнем проверку статусов домашних работ."
    send_message(bot, message)
    logger.info(message)
    last_message = ""

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get("current_date", int(time.time()))
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = "Без изменений."
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logger.info(message)

        except Exception as error:
            message = f"Сбой в работе программы: {error}"
            logger.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == "__main__":
    main()
