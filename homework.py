import logging
import os
import sys
import time
from http import HTTPStatus

import requests
import telegram
from dotenv import load_dotenv
from telegram import Bot, TelegramError

import exceptions

load_dotenv()


PRACTICUM_TOKEN: str = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN: str = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID: str = os.getenv('TELEGRAM_CHAT_ID')


RETRY_PERIOD: int = 600
ENDPOINT: str = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS: dict[str, str] = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_VERDICTS: dict[str, str] = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.',
}


def check_tokens() -> bool:
    """Проверка доступности переменных окружения."""
    return all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID])


def send_message(bot: Bot, message: str) -> None:
    """Отправка сообщения в Telegram чат."""
    try:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)
        logging.debug('Сообщение о статусе отправлено.')
    except TelegramError as error:
        logging.error(f'Сбой при отправке сообщения в Telegram: {error}')
        raise exceptions.SendMessageError(f'Сбой при отправке сообщения '
                                          f'в Telegram: {error}')


def get_api_answer(timestamp: int) -> list[str]:
    """Запрос к эндпоинту API-сервиса."""
    cur_timestamp = timestamp or int(time.time())
    params = {'from_date': cur_timestamp}
    logging.info('Выполняется запрос к эндпоинту API-сервиса.')
    try:
        homework_statuses = requests.get(
            ENDPOINT, headers=HEADERS, params=params
        )
        if homework_statuses.status_code != HTTPStatus.OK:
            raise exceptions.EndpointError(f'Ошибка доступа: '
                                           f'{homework_statuses.status_code}.')
        return homework_statuses.json()
    except Exception:
        raise SystemError(
            f'Эндпоинт недоступен. Код ошибки {homework_statuses.status_code}'
        )


def check_response(response: dict[str, list]) -> list[str]:
    """Проверка ответа API на корректность."""
    if not isinstance(response, dict):
        raise TypeError('Переменная не является словарем.')
    try:
        homeworks = response['homeworks']
    except KeyError:
        raise KeyError('Ключ homeworks отсутствует.')
    if not isinstance(homeworks, list):
        raise TypeError('Список домашних работ не является типом list.')
    return homeworks


def parse_status(homework: list[str]) -> str:
    """Извлечение информации о статусе домашней работы."""
    if 'homework_name' not in homework:
        raise KeyError('Данная работа отсутствует в списке.')
    homework_name = homework.get('homework_name')
    homework_status = homework.get('status')
    if homework_status not in HOMEWORK_VERDICTS:
        raise ValueError(f'Статуса {homework_status} не существует.')
    return (
        f'Изменился статус проверки работы "{homework_name}". '
        f'{HOMEWORK_VERDICTS[homework_status]}'
    ).format(homework_name=homework_name)


def main() -> None:
    """Основная логика работы бота."""
    if not check_tokens():
        logging.critical('Недоступны переменные окружения.')
        sys.exit('Недоступны переменные окружения.')
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    message = 'Начнем проверку статусов домашних работ.'
    send_message(bot, message)
    logging.info(message)
    last_message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            timestamp = response.get('current_date', int(time.time()))
            homeworks = check_response(response)
            if homeworks:
                message = parse_status(homeworks[0])
            else:
                message = 'Без изменений.'
            if message != last_message:
                send_message(bot, message)
                last_message = message
            else:
                logging.info(message)

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            logging.error(message)
            if message != last_message:
                send_message(bot, message)
                last_message = message
        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s, %(levelname)s, %(message)s, %(name)s',
        encoding='utf--8',
        handlers=[logging.StreamHandler(sys.stdout)]
    )

    main()
