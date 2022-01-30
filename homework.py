import os
import time
import sys
import logging
import requests
import telegram

from dotenv import load_dotenv


load_dotenv()

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s'
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stderr)
logger.addHandler(handler)


PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TOKEN')
TELEGRAM_CHAT_ID = os.getenv('chat_id')

RETRY_TIME = 600
ENDPOINT = (
    'https://practicum.yandex.ru/api/user_api/'
    'homework_statuses/'
)
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}


HOMEWORK_STATUSES = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}


def send_message(bot, message):
    """Отправка сообщения."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
    except Exception:
        logging.error('Сбой при отправке сообщения в Telegram:')


def get_api_answer(current_timestamp):
    """Api запрос к практикуму."""
    # переменная в котором настоящее время
    timestamp = current_timestamp or int(time.time())
    params = {'from_date': timestamp}
    try:
        homework = requests.get(
            ENDPOINT,
            headers=HEADERS,
            params=params
        )
    except Exception:
        raise Exception('любые другие сбои при запросе к эндпоинту')

    if homework.status_code != 200:
        raise Exception(f'недоступность эндпоинта {ENDPOINT}')

    try:
        return homework.json()
    except Exception:
        raise Exception('ошибка, тело не в json формате')


def check_response(response):
    """Проверка вернувшегося ответа от практикума."""
    if len(response) == 0:
        raise Exception('Ответ пришел пустой')
    # isinstance проверка типа значения первого аргумента
    if isinstance(response, list):
        response = response[0]

    homeworks = response.get('homeworks')
    if not isinstance(homeworks, list):
        raise Exception("homework не является списком")
    if len(homeworks) == 0:
        raise Exception('Список с домашкой пуст')

    return homeworks[0]


def parse_status(homework):
    """Достаем из домашки нужную информацию."""
    if 'status' not in homework:
        raise KeyError('Пустое значение status')
    if 'homework_name' not in homework:
        raise KeyError('Пустое значение homework_name')
    if homework['status'] not in HOMEWORK_STATUSES:
        raise Exception('недокументированный статус домашней работы, '
                        'обнаруженный в ответе API'
                        )
    homework_name = homework['homework_name']
    homework_status = homework['status']
    verdict = HOMEWORK_STATUSES[homework_status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def check_tokens():
    """Проверка токенов."""
    # общая проверка наличия парамметров
    if not all([PRACTICUM_TOKEN, TELEGRAM_TOKEN, TELEGRAM_CHAT_ID]):
        logging.critical('Отсутствует обязательная переменная окружения: '
                         'PRACTICUM_TOKEN '
                         'Программа принудительно остановлена.')
        return False

    return True


def main():
    """Основная логика работы бота."""
    # Создание бота
    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    if not check_tokens():
        return
    status = ''
    while True:
        try:
            # присваеваем текущее время
            current_timestamp = int(time.time())
            response = get_api_answer(current_timestamp)
            homework = check_response(response)
            message = parse_status(homework)
            if status != message:
                logging.info('Сообщение о новом статусе проверки отправлено')
                send_message(bot, message)
            logging.debug('отсутствие в ответе новых статусов')

        except Exception as error:
            message = f'Сбой в работе программы: {error}'
            send_message(bot, message)
            logging.info('Сообщение о ошибке отправлено')
            logging.exception('Ошибка:')
        else:
            status = message
        finally:
            time.sleep(RETRY_TIME)


if __name__ == '__main__':
    main()
