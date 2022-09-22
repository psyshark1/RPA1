from sap_web import FioriInbox
from business.models.dto import ReflectTask
from db.logger import logger
from logger import log
from requests import HTTPError


class FioriInboxExec(FioriInbox):

    def __init__(self, session, headers):
        super().__init__(session=session, headers=headers)

    def exec_task(self, task: ReflectTask, proc_id: str)-> int:

        logger.set_log(task.number_45, 'SAP Fiori', 'stage11', 'exec_task', 'Info', 'Выполнение 214* в SAP FIORI', 'Начало работы')
        #log.add(level='INFO', dir_path=LOGS_DIR)
        log.exception(f'{task.number_45} - Выполнение 214* в SAP FIORI - Старт выполнения')

        process = next((i for i in self.get_inbox_data() if i["processuuid"] == proc_id), None)
        if not process:
            logger.set_log(task.number_45, 'SAP Fiori', 'stage11', 'exec_task',
                           'Error', 'Выполнение 214* в SAP FIORI', 'Номер процесса не найден')
            log.exception(f'{task.number_45} - Выполнение 214* в SAP FIORI - Ошибка выполнения: Номер процесса не найден')
            task.status = '2'
            task.comment = task.comment + f'Ошибка выполнения {task.number_214}: Номер процесса не найден'
            return 0

        try:
            self.execute_process(process["InstanceID"])
        except HTTPError as e:
            logger.set_log(task.number_45, 'SAP Fiori', 'stage11', 'exec_task',
                           'Error','Выполнение 214* в SAP FIORI',e)
            log.exception(f'{task.number_45} - Выполнение 214* в SAP FIORI - Ошибка выполнения: {e}')
            task.status = '2'
            task.comment = task.comment + f'Ошибка выполнения {task.number_214}: {e}'
            return -1

        task.status = '3'
        task.comment = task.comment + "Выполнено;"

        logger.set_log(task.number_45, 'SAP Fiori', 'stage11', 'exec_task', 'Info', 'Выполнение 214* в SAP FIORI', 'Завершение работы')
        log.info(f'{task.number_45} - Процесс 214* в SAP FIORI выполнен')
        return 1
