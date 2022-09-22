import socket

import pyodbc

from config import ENV_DATA, ROBOT_NAME


class AppLaunchStatus:
    """Таблица запусков"""
    __table = 'App_LaunchStatus'

    def __init__(self, module_name: str):
        self.__robot_name = ROBOT_NAME
        self.__proc_name = module_name
        self.__vm_name = socket.gethostname()
        self.__dsn = ENV_DATA['db_dsn']

    def get_status_work(self) -> list:
        """Возвращает статус запуска"""
        with pyodbc.connect(self.__dsn) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"SELECT * FROM {self.__table} WHERE vmName = '{self.__vm_name}' AND "
                f"procName = '{self.__proc_name}' AND robotName = '{self.__robot_name}' AND launchStatus = 1"
            )
            return cursor.fetchall()

    def set_start_status_work(self, tab_num: str):
        """Устанавливает статус запуска"""
        with pyodbc.connect(self.__dsn) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"INSERT INTO {self.__table} (vmName, robotName, procName, tabnum, launchStatus, dt_Open) "
                f"VALUES ('{self.__vm_name}', '{self.__robot_name}', '{self.__proc_name}', "
                f"'{tab_num}', 1, GETDATE())"
            )
            connection.commit()

    def set_cnt_request(self, quantity: int):
        """Устанавливает общее количество операций на обрабоку"""
        with pyodbc.connect(self.__dsn) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"UPDATE {self.__table} SET cntRequest = '{quantity}' "
                f"WHERE vmName = '{self.__vm_name}' AND robotName = '{self.__robot_name}' AND "
                f"procName = '{self.__proc_name}' AND launchStatus = 1"
            )
            connection.commit()

    def update_cnt_good(self, quantity: int):
        """Обновляет количество успешно обработанных операций"""
        with pyodbc.connect(self.__dsn) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"UPDATE {self.__table} SET cntGood = '{quantity}' "
                f"WHERE vmName = '{self.__vm_name}' AND robotName = '{self.__robot_name}' AND "
                f"procName = '{self.__proc_name}' AND launchStatus = 1"
            )
            connection.commit()

    def set_end_status_work(self):
        """Устанавливает статус завершения работы"""
        with pyodbc.connect(self.__dsn) as connection:
            cursor = connection.cursor()
            cursor.execute(
                f"UPDATE {self.__table} SET launchStatus = 0, dt_Close = GETDATE() "
                f"WHERE vmName = '{self.__vm_name}' AND robotName = '{self.__robot_name}' AND "
                f"procName = '{self.__proc_name}' AND launchStatus = 1"
            )
            connection.commit()
