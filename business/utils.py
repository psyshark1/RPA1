import datetime
import glob
import os
import shutil
from typing import Union

from sap_web import parse_between

from config import TEMP_DIR


def decode_date(fiori_date: str) -> Union[datetime.datetime, None]:
    """
    Метод конвертит юникс тайм в datetime.
    :param fiori_date: юникс тайм обернутый в '/Date(<нужный нам юникс тайм>)/', а иногда в '/Date(<нужный нам юникс тайм>+0000)/'
    :return: объект datetime or None
    """

    timestamp = parse_between(start='/Date\(', stop='\)/', text=fiori_date).replace('+0000', '')

    if timestamp:
        return datetime.datetime.utcfromtimestamp(int(str(timestamp)[:-3]))
    return None


def to_float(value: str) -> Union[None, float]:
    """
    Метод приводит флоат в строке в нормальныйц формат
    :param value: флоат в строке
    :return: float
    """
    try:
        return float(value.replace(' ', '').replace(',', '.'))
    except:
        return None


def remove_temp(full_clear: bool = False):
    """
    Полностью очищает папку _temp
    :param full_clear: если False то удаляет только файлы из корня если True то удаляет полность папку.
    :return:
    """
    for filename in os.listdir(TEMP_DIR):
        file_path = os.path.join(TEMP_DIR, filename)
        try:
            if not full_clear:
                os.unlink(file_path)
            else:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)
        except Exception as e:
            print('Не смог удалить файл %s. Причина: %s' % (file_path, e))
