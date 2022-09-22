import sys
import os

import pyodbc
#from loguru import logger

#sys.path.append(f'C:\\Users\\{os.getlogin()}\\PycharmProjects\\RPA-1079\\reflect-kz-automation')

from config import ENV_DATA


class Procedure:
    """Класс процедур, связанных с базой данных."""

    @staticmethod
    #@logger.catch()
    def execute_sql_read(request: str) -> list:
        """
        Возвращает список строк

        :param request: SQL запрос
        :return:
        """

        with pyodbc.connect(ENV_DATA['db_dsn']) as connection:
            cursor = connection.cursor()
            cursor.execute(request)

            return cursor.fetchall()

    @staticmethod
    #@logger.catch()
    def execute_sql_write(request: str):
        """
        Записывает данные
        """
        with pyodbc.connect(ENV_DATA['db_dsn']) as connection:
            cursor = connection.cursor()
            cursor.execute(request)
            connection.commit()

    ''''@staticmethod
    #@logger.catch()
    def send_email(auth_data: str, recipients: str, subject: str, body: str):
        """
        Метод по отправке уведоммлений на почту через базу данных MS SQL.

        :param auth_data: Данный для авторизации
        :param recipients: Получатели сообщений
        :param subject: Тема сообщения
        :param body: Тело сообщения
        """
        replaced_body = body.replace("'", '"')

        with pyodbc.connect(auth_data) as connection:
            cursor = connection.cursor()
            cursor.execute(
                "EXEC [SSC-Data].[dbo].sendUserMessage "
                f"@userEmail = '{recipients}', @subjectMsg = '{subject}', @msg = '{replaced_body}'"
            )'''

