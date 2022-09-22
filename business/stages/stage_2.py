import re
from typing import Union

from logger import log

from business.check_documents_in_edo.constants import VERSION_HEADER_L_ID
from business.check_documents_in_edo.parsers import WebGuiParser
from db.logger import logger
from bs4 import BeautifulSoup

from business.models.dto import ReflectTask, TaskDeliveryVolume
from business.models.sap_web_additions import BaseAdditions
from config import ENV_DATA


class Stage2(BaseAdditions):
    """Этап 2. Получить данные для проверки создания 18* частичная поставка (вх. поставка VL33N)"""

    def __init__(self, task: ReflectTask, session=None):
        """
        Конструктор

        :param task: Задание
        :param session: (Опционально) Объект сесии
        """

        #log.add(dir_path=LOGS_DIR / f'log_{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}.log', level='DEBUG')
        super(Stage2, self).__init__( session=session)

        self.task = task

        if not session:
            self.login(ENV_DATA['sap_gui_login'], ENV_DATA['sap_gui_pass'])

        self.open_home_page()

    @log.write_by_method
    def get_check_data(self) -> Union[ReflectTask, None]:
        """
        Открывает транзакцию VL33N и получает значения завода, номера 50* и объемов

        :return: Объект задания или None
        """

        log.info('Этап 2. Запуск.')

        if self.task.delivery_type == 2:

            # Открытие транзакции
            self.open_transaction('VL33N', True)
            log.info('Этап 2. Открытие транзакции VL33N.')
            logger.set_log(self.task.number_45, 'SAP S4', 'stage2', 'get_check_data', 'Info', 'Получение завода, номера 50* и объемов', 'Открытие транзакции VL33N')

            # Ввод number 18
            self.send_template_request(
                json=[
                    {"post": "value/wnd[0]/usr/ctxtLIKP-VBELN", "content": f"{self.task.number_18}", "logic": "ignore"}
                ]
            )

            response = self.send_template_request(
                json=[
                    {"content": "", "post": "value/wnd[0]/usr/ctxtLIKP-VBELN"},
                    {"content": f"{self.task.number_18}", "post": "value/wnd[0]/usr/ctxtLIKP-VBELN"},
                    {"post": "action/304/wnd[0]/usr/ctxtLIKP-VBELN", "content": f"position={len(self.task.number_18)}", "logic": "ignore"},
                    {"post": "focus/wnd[0]/usr/ctxtLIKP-VBELN", "logic": "ignore"},
                    {"post": "vkey/0/ses[0]"},
                    {"get": "state/ur"}
                ]
            )

            if len(response) == 6:
                r = re.findall(r'rowCount:(\d{1,3}),', response[-1]['content'], flags=re.IGNORECASE)
                if len(r) != 0:
                    table_rowcount = int(r[0])
                else: return self.error('Этап 2. Позиции не найдены','Получение позиций материла','Позиции материла не найдены в транзакции VL33N')
                r = re.findall(r'vcrc="(\d{1,3})"', response[-1]['content'], flags=re.IGNORECASE)
                if len(r) != 0:
                    visible_rowcount = int(r[0])
                else: return self.error('Этап 2. Позиции не найдены','Получение позиций материла','Позиции материла не найдены в транзакции VL33N')
            else:
                return self.error('Этап 2. Позиции не найдены','Получение позиций материла','Позиции материла не найдены в транзакции VL33N')

            volume_list = []
            parser = WebGuiParser()
            checked_rowcount = visible_rowcount

            while checked_rowcount <= table_rowcount + visible_rowcount:
                res = parser.parse_webgui_table(cdata=response[-1]['content'],
                                                 header_left_id='M0:46:2:3B256:2-mrss-hdr-left-content',
                                                 header_right_id='M0:46:2:3B256:2-mrss-hdr-none-content',
                                                 body_right_id='M0:46:2:3B256:2-mrss-cont-none-content',
                                                 body_left_id='M0:46:2:3B256:2-mrss-cont-left-content')

                if len(list(filter(lambda x: not x['Поз.'], res))) != 0:
                    positions = list(filter(lambda x: x['Поз.'], res))
                    values = list(map(lambda x: TaskDeliveryVolume(buy_document=x['ДокументОбразец'],
                                                                   pos_prd_doc=x['ПозПрдДок'],
                                                                   delivery_volume=x['Объем поставки'],
                                                                   ), positions))
                    volume_list += values


                    '''volume_list[i].buy_document = res[i]['ДокументОбразец']
                    volume_list[i].pos_prd_doc = res[i]['ПозПрдДок']
                    volume_list[i].delivery_volume = res[i]['Объем поставки']'''

                else:
                    values = list(map(lambda x: TaskDeliveryVolume(buy_document=x['ДокументОбразец'],
                                                               pos_prd_doc=x['ПозПрдДок'],
                                                               delivery_volume=x['Объем поставки'],
                                                               ), res))
                    volume_list += values

                response = self.send_template_request(
                    json=[
                        {"post":"action/61/wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01/ssubSUBSCREEN_BODY:SAPMV50A:1202/tblSAPMV50ATC_LIPS_OVER_INB","content":f"position={str(checked_rowcount)}"},
                        {"get": "state/ur"}]
                )
                checked_rowcount += checked_rowcount

            self.task.factory = res[0]['З-д']

            log.info(f'Этап 2. Список объемов поставки получен')

            self.task.volume_list = volume_list

            response = self.send_template_request(
                json=[
                    {"post": "action/304/wnd[0]/usr/subSUBSCREEN_HEADER:SAPMV50A:1602/ctxtLIKP-LIFNR",
                     "content": "position=0", "logic": "ignore"},
                    {"post": "focus/wnd[0]/usr/subSUBSCREEN_HEADER:SAPMV50A:1602/ctxtLIKP-LIFNR", "logic": "ignore"},
                    {"post": "vkey/7/wnd[0]"},
                    {"get": "state/ur"}
                ]
            )

            num50 = re.search('ПМ ПоступлМатериала \d+', response[3]['content'])

            if num50 is not None:
                self.task.number_50 = re.search('ПМ ПоступлМатериала \d+', response[3]['content'])[0][20:]
            else:
                return self.error('Этап 2. Номер 50 не найден','Получение завода, номера 50* и объемов','Номер 50 не найден в транзакции VL33N')

            log.info(f'Этап 2. Номер 50 = {self.task.number_50}')
            logger.set_log(self.task.number_45, 'SAP S4', 'stage2', 'get_check_data', 'OK', 'Получение завода, номера 50* и объемов','Данные получены')
            self.send_template_request(json=[{"post":"action/3/wnd[0]/tbar[0]/btn[15]"},{"get":"state/ur"}])
        else:
            log.warning('Этап 2. Не запущен - тип поставки не равен 2.')
            logger.set_log(self.task.number_45, 'SAP S4', 'stage2', 'get_check_data', 'Warning', 'Получение завода, номера 50* и объемов','Не запущен - тип поставки не равен 2')

        log.info('Этап 2. Конец.')
        return self.task

    def error(self, gen_mess: str, step: str, options: str):
        log.error(gen_mess)
        logger.set_log(self.task.number_45, 'SAP S4', 'stage2', 'get_check_data', 'Error',
                       step, options)
        self.send_template_request(json=[{"post": "action/3/wnd[0]/tbar[0]/btn[15]"}, {"get": "state/ur"}])
        self.task.status = '2'
        if self.task.comment is None:
            self.task.comment = options + ';'
        else:
            self.task.comment = self.task.comment + options + ';'
        log.info('Этап 2. Конец.')
        return self.task
