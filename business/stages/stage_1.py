from datetime import datetime

from logger import log

from business.models.db import Procedure
from business.models.dto import ReflectTask
from db.logger import logger


class Stage1:
    """Этап 1. Получить задание"""

    def __init__(self):
        """Конструктор"""

        self.db = Procedure()
        # log.add(dir_path=LOGS_DIR / f'log_{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}.log', level='DEBUG')

    # @log.write_by_method
    def get_task(self):
        """
        Получает из БД список заданий

        :return: Возвращает None при ошибке подключения к БД
        """

        log.info('Этап 1. Запуск.')
        tasks_list = self.db.execute_sql_read("SELECT * FROM RPA1079_Tasks WHERE Status = '1'")
        log.info(f'Этап 1. Количество заданий - {len(tasks_list)}.')
        lst = []
        if tasks_list:
            for index, task in enumerate(tasks_list):
                log.info(f'Этап 1. Задание {index + 1}/{len(tasks_list)}: {task}')
                lst.append(
                    ReflectTask(id=int(task[0]),
                                number_45=task[1],
                                number_18=task[2],
                                date_18=task[3],
                                edo_numbers=task[4],
                                user_fio=task[6],
                                delivery_date=task[7],
                                delivery_type=int(task[8]),
                                # edo_documents_count=int(task[12]),
                                complete_datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                ))
        #         yield ReflectTask(
        #             id=int(task[0]),
        #             number_45=task[1],
        #             number_18=task[2],
        #             date_18=task[3],
        #             edo_numbers=task[4],
        #             user_fio=task[6],
        #             delivery_date=task[7],
        #             delivery_type=int(task[8]),
        #             edo_documents_count=int(task[12]),
        #             complete_datetime=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        #         )
        else:
            log.warning('Этап 1. Список заданий пуст.')
            logger.set_log('', 'Python', 'stage1', 'get_task', 'Warning', 'Получение списка задач',
                           'Список заданий пуст', )
            return lst

        log.info('Этап 1. Конец.')
        logger.set_log('', 'Python', 'stage1', self.get_task.__name__, 'OK', 'Получение списка заданий',
                       'Задания получены')
        return lst
