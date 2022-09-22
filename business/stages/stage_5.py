from bs4 import BeautifulSoup
from logger import log

from business.models.db import Procedure
from business.models.dto import ReflectTask, TaskContractor
from business.models.sap_web_additions import BaseAdditions
from config import ENV_DATA
from db.logger import logger


class Stage5(BaseAdditions):
    """Этап 5. Получить данные контрагента"""

    def __init__(self, task: ReflectTask, session=None):
        """
        Коструктор

        :param task: Задание
        :param session: (Опционально) Объект сесии
        """

        super(Stage5, self).__init__(session=session)

        self.task = task
        self.task_contractor = TaskContractor()
        self.db = Procedure()

        if not session:
            self.login(ENV_DATA['sap_gui_login'], ENV_DATA['sap_gui_pass'])

        self.open_home_page()

    @log.write_by_method
    def get_contractor_data(self) -> ReflectTask:
        """
        Получение данных контрагента

        :return: Объект задания
        """
        log.info('Этап 5. Запуск.')

        contractor_requisites = self.db.execute_sql_read(
            f"SELECT * FROM RPA1079_Contractor_Requisites WHERE Zavod = '{self.task.factory}'"
        )

        contractor = str(contractor_requisites[0][2])
        self.task_contractor.subscriber = contractor_requisites[0][3]
        log.info(
            f'Этап 5. Реквизиты контрагента:\n'
            f'\tКонтрагент = {contractor}\n'
            f'\tПодписант = {self.task_contractor.subscriber}'
        )

        self.open_transaction('BP')
        log.info('Этап 5. Открытие транзакции "BP - Просмотр делового партнера".')
        logger.set_log(self.task.number_45, 'SAP S4', 'stage5', 'get_contractor_data', 'Info', 'Получение данных контрагента', 'Открытие транзакции BP')

        # Открытие Делового партнера

        self.send_template_request(
            json=[
                {
                    "post": "action/304/wnd[0]/usr/subSCREEN_3000_RESIZING_AREA:SAPLBUS_LOCATOR:2036/subSCREEN_1010_RIGHT_AREA:SAPLBUPA_DIALOG_JOEL:1000/subSCREEN_1000_HEADER_AREA:SAPLBUPA_DIALOG_JOEL:1510/ctxtBUS_JOEL_MAIN-CHANGE_NUMBER",
                    "content": "position=0",
                    "logic": "ignore"
                },
                {
                    "post": "focus/wnd[0]/usr/subSCREEN_3000_RESIZING_AREA:SAPLBUS_LOCATOR:2036/subSCREEN_1010_RIGHT_AREA:SAPLBUPA_DIALOG_JOEL:1000/subSCREEN_1000_HEADER_AREA:SAPLBUPA_DIALOG_JOEL:1510/ctxtBUS_JOEL_MAIN-CHANGE_NUMBER",
                    "logic": "ignore"
                },
                {"post": "action/3/wnd[0]/tbar[1]/btn[17]"},
                {"get": "state/ur"}
            ]
        )

        self.send_template_request(
            json=[
                {
                    "post": "value/wnd[1]/usr/ctxtBUS_JOEL_MAIN-OPEN_NUMBER",
                    "content": f"{contractor}",
                    "logic": "ignore"
                }
            ]
        )

        response = self.send_template_request(
            json=[
                {
                    "content": f"{contractor}",
                    "post": "value/wnd[1]/usr/ctxtBUS_JOEL_MAIN-OPEN_NUMBER"
                },
                {
                    "post": "action/304/wnd[1]/usr/ctxtBUS_JOEL_MAIN-OPEN_NUMBER",
                    "content": f"position={len(contractor)}",
                    "logic": "ignore"
                },
                {
                    "post": "focus/wnd[1]/usr/ctxtBUS_JOEL_MAIN-OPEN_NUMBER",
                    "logic": "ignore"
                },
                {"post": "vkey/0/ses[0]"},
                {"get": "state/ur"}
            ]
        )

        soup = BeautifulSoup(response[4]['content'], 'lxml')


        self.task_contractor.name = ' '.join(
            map(
                lambda i: soup.find('input', id=f'M0:46:1:2:2:2:1:2B256:1:2::{i}:21').get('value', ''), 
                range(4)
            )
        ).lower()
        self.task_contractor.inn = soup.find('input', id='M0:46:1:2:2:2:1:2B256:1:11::0:21')['value'].lower()
        self.task_contractor.kpp = soup.find('input', id='M0:46:1:2:2:2:1:2B256:1:11::0:42')['value'].lower()
        self.task_contractor.street = self.__get_correct_name(
            soup.find('input', id='M0:46:1:2:2:2:1:2B256:1:13:1:1::0:22')['value'],
            [i[0] for i in self.db.execute_sql_read('select street from Abbreviation where street is not NULL')]
        ).lower()
        self.task_contractor.house = self.__get_correct_name(
            soup.find('input', id='M0:46:1:2:2:2:1:2B256:1:13:1:1::0:55')['value'],
            [i[0] for i in self.db.execute_sql_read('select house from Abbreviation where house is not NULL')]
        ).lower()
        self.task_contractor.city = self.__get_correct_name(
            soup.find('input', id='M0:46:1:2:2:2:1:2B256:1:13:1:1::1:33')['value'],
            [i[0] for i in self.db.execute_sql_read('select city from Abbreviation where city is not NULL')]
        ).lower()

        self.task.contractor = self.task_contractor
        log.info(
            f'Этап 5. Данные контрагента:\n'
            f'\tИмя = {self.task_contractor.name}\n'
            f'\tИНН = {self.task_contractor.inn}\n'
            f'\tКПП = {self.task_contractor.kpp}\n'
            f'\tУлица = {self.task_contractor.street}\n'
            f'\tДом = {self.task_contractor.house}\n'
            f'\tГород = {self.task_contractor.city}'
        )
        self.send_template_request(json=[{"post":"action/3/wnd[0]/tbar[0]/btn[15]"},{"get":"state/ur"}])
        logger.set_log(self.task.number_45, 'SAP S4', 'stage5', 'get_contractor_data', 'Info','Получение данных контрагента', 'Данные контрагента получены')
        log.info('Этап 5. Конец.')
        return self.task

    def __get_correct_name(self, base_string: str, templates: list) -> str:
        """
        Метод для вычлинения из базовой строки лишних шаблонов
        :param base_string: Строка, из которой будут вычленять шаблоны.
        :param templates: Список шаблонов для вычлинения (В нижнем регистре).
        :return: Строка-результат.
        """

        for word in base_string.split(' '):
            if word.lower() in templates:
                return base_string.replace(word, '').replace(' ', '')

        return base_string
