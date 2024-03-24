from http import HTTPStatus
import logging
import os
import sys
import time

from dotenv import load_dotenv
import requests
import telegram


load_dotenv()

PRACTICUM_TOKEN = os.getenv('PRACTICUM_TOKEN')
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

RETRY_PERIOD = 600
ENDPOINT = 'https://practicum.yandex.ru/api/user_api/homework_statuses/'
HEADERS = {'Authorization': f'OAuth {PRACTICUM_TOKEN}'}

HOMEWORK_VERDICTS = {
    'approved': 'Работа проверена: ревьюеру всё понравилось. Ура!',
    'reviewing': 'Работа взята на проверку ревьюером.',
    'rejected': 'Работа проверена: у ревьюера есть замечания.'
}

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s, %(levelname)s, %(message)s',
    encoding='utf-8',
    stream=sys.stdout
)

logger = logging.getLogger(__name__)


def check_tokens():
    """Проверить доступ переменных окружения."""
    if (PRACTICUM_TOKEN is None or PRACTICUM_TOKEN == ''
            and TELEGRAM_TOKEN is None or TELEGRAM_TOKEN == ''
            and TELEGRAM_CHAT_ID is None or TELEGRAM_CHAT_ID == ''):
        return False

    return True


def send_message(bot, message):
    """Отправить сообщение в Telegram чат."""
    try:
        bot.send_message(TELEGRAM_CHAT_ID, message)
        logger.debug('Сообщение отправлено')
        return True

    except Exception as error:
        logger.error(f'Сообщение не отправлено: {error}')
        return False


def get_api_answer(timestamp):
    """Сделать GET запрос к эндпойнту."""
    try:
        response = requests.get(url=ENDPOINT,
                                headers=HEADERS,
                                params={'from_date': timestamp})
        logger.info('GET запрос выполнен успешно')

    except requests.RequestException as error:
        raise ConnectionError(error)

    if response.status_code != HTTPStatus.OK:
        raise requests.HTTPError('Неверный статус GET запроса')

    return response.json()


def check_response(response):
    """Проверить ответ API на соответствие документации из урока."""
    if not isinstance(response, dict):
        raise TypeError('Ответ API не является словарем (формат JSON)')
    if 'homeworks' not in response.keys():
        raise KeyError('В ответе API нет ключа "homeworks"')
    if not isinstance(response['homeworks'], list):
        raise TypeError('Значение ключа "homeworks" не является списком')

    return response['homeworks'][0]


def parse_status(homework):
    """Извлечь статус рассматриваемой работы."""
    if homework is None:
        raise IndexError('Этого домашнего задания не существует')

    homework_name = homework.get('homework_name')
    status = homework.get('status')

    if homework_name is None or homework_name == '':
        raise KeyError('Значение ключа "homework_name" не существует')
    if status is None or status == '':
        raise KeyError('Значение ключа "status" не существует')
    if status not in HOMEWORK_VERDICTS:
        raise KeyError(f'В ответе API неожиданный статус: {status}')

    verdict = HOMEWORK_VERDICTS[status]
    return f'Изменился статус проверки работы "{homework_name}". {verdict}'


def main():
    """Основная логика работы бота."""
    if not check_tokens():
        logger.critical('Переменные окружения не установлены')
        sys.exit()

    bot = telegram.Bot(token=TELEGRAM_TOKEN)
    timestamp = int(time.time())
    status = ''
    message = ''

    while True:
        try:
            response = get_api_answer(timestamp)
            check_resp = check_response(response)
            if check_resp:
                updated_status = parse_status(check_resp)

                if updated_status != status:
                    send_message(bot, updated_status)
                    status = updated_status
                else:
                    logger.debug('Статус домашней работы не обновился')

        except Exception as error:
            updated_message = f'Сбой в работе программы: {error}'
            if updated_message != message:

                if send_message(bot, updated_status):
                    message = updated_message
                logger.error(message)

        finally:
            time.sleep(RETRY_PERIOD)


if __name__ == '__main__':
    main()
