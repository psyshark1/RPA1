import os
from pathlib import Path

from dotenv import dotenv_values

# Корневая директория проекта
ROOT = Path(__file__).resolve().parent

# Данные .env
ENV_DATA = dotenv_values(ROOT / '.env')

# Директория для записи логов
LOGS_DIR = ROOT / '_logs'

# Директория временных файлов
TEMP_DIR = ROOT / '_temp'

# Директория с рабочими файлами и справочниками
WORK_DIR = ROOT / '_data'

# Директория с рабочими файлами и справочниками
DOC_DIR = ROOT / '_documents'

# Директория с xsd схемами для валидации xml
XSD_SCHEMAS_DIR = ROOT / 'xsd-schemas'

# Email для отправки писем об ошибках
USER_EMAIL = ('')
# Email отправителя писем об ошибках
EMAIL_SENDER = ''

TEMP_DOC = 'temp_doc.pdf'

MONTHS = {
    '01': 'января',
    '02': 'февраля',
    '03': 'марта',
    '04': 'апреля',
    '05': 'мая',
    '06': 'июня',
    '07': 'июля',
    '08': 'августа',
    '09': 'сентября',
    '10': 'октября',
    '11': 'ноября',
    '12': 'декабря',
}

ROBOT_NAME = ''

