from datetime import datetime

import pyodbc
from config import ENV_DATA, ROBOT_NAME


class Logger:
    def __init__(self):
        self.__robot_name = ROBOT_NAME
        self.__table = 'App_Logs'
        self.__dsn = ENV_DATA['db_dsn']

    def set_log(self, id_task, sys_name, module_name, proc_name, status, step, options):
        """
        Метод запускает инсерт в таблицу AppStatus
        :param id_task: Идентификатор выполняемой задачи
        :param sys_name: Название Робота
        :param module_name: Название выполняемого модуля
        :param proc_name: Название метода
        :param status: Статус выполнения
        :param step: Шаг
        :param options: Результат
        :return:
        """

        self.__log_insert(id_task, sys_name, module_name, proc_name, status, step, options)

    def __if_row_exist(self, id_task, sys_name, module_name, proc_name, status, step, options) -> bool:
        """
        Метод проверяет существует ли строка в базе
        :param id_task: Идентификатор выполняемой задачи
        :param sys_name: Название Робота
        :param module_name: Название выполняемого модуля
        :param proc_name: Название метода
        :param status: Статус выполнения
        :param step: Шаг
        :param options: Результат
        :return: True or False
        """
        with pyodbc.connect(self.__dsn) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT Idtask,appName,sysName,module,procName,status,step,options FROM {self.__table} WHERE "
                f"IdTask = \'{str(id_task)}\' AND appName = \'{self.__robot_name}\' AND sysName = \'{sys_name}\' AND procName = \'{module_name}\' AND "
                f"procName = \'{proc_name}\' AND status = \'{status}\' AND step = \'{step}\' AND options = \'{options}\'"
            )
            row_count = cursor.rowcount

            if not row_count:
                return True

            return False

    def __log_insert(self, id_task, sys_name, module_name, proc_name, status, step, options):
        """
        Метод инсертит в таблицу App_Logs
        :param id_task: Идентификатор выполняемой задачи
        :param sys_name: Название Робота
        :param module_name: Название выполняемого модуля
        :param proc_name: Название метода
        :param status: Статус выполнения
        :param step: Шаг
        :param options: Результат
        :return:
        """

        if not self.__if_row_exist(id_task, sys_name, module_name, proc_name, status, step, options):
            return

        with pyodbc.connect(self.__dsn) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"INSERT INTO {self.__table} (Idtask,appName,sysName,module,procName,status,step,options,changeDate,changeTime) VALUES "
                f"(\'{str(id_task)}\',\'{self.__robot_name}\',\'{sys_name}\',\'{module_name}\',\'{proc_name}\',\'{status}\',\'{step}\',\'{options}\',"
                f"\'{datetime.today().strftime('%Y-%m-%d')}\',\'{datetime.today().strftime('%H:%M:%S')}\')"
            )
            connection.commit()


logger = Logger()
