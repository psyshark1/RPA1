import re
from typing import Union

from logger import log
from bs4 import BeautifulSoup

from business.models.dto import ReflectTask
from business.models.sap_web_additions import BaseAdditions
from config import ENV_DATA
from db.logger import logger


class Stage4(BaseAdditions):
    """Этап 4. Получить завод. Выполнить транзакцию ME2N"""

    def __init__(self, task: ReflectTask, session=None):
        """
        Конструктор

        :param task: Задание
        :param session: (Опционально) Объект сесии
        """

        #log.add(dir_path=LOGS_DIR / f'log_{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}.log', level='DEBUG')
        super(Stage4, self).__init__(session=session)

        self.task = task

        if not session:
            self.login(ENV_DATA['sap_gui_login'], ENV_DATA['sap_gui_pass'])

        self.open_home_page()

    @log.write_by_method
    def get_factory(self) -> Union[ReflectTask, None]:
        """
        Открывает транзакцию ME2N и получает значение завода

        :return: Задание или None
        """

        log.info('Этап 4. Запуск.')

        if self.task.delivery_type == 1:

            # Открываем транзакцию

            self.open_transaction('ME2N')
            log.info('Этап 4. Открытие транзакции ME2N.')
            logger.set_log(self.task.number_45, 'SAP S4', 'stage4', 'get_factory', 'Info', 'Получение значения завода','Открытие транзакции ME2N')

            self.__clear_form()

            # Вводим значение документа закупки и жмем выполнить

            self.send_template_request(
                json=[
                    {
                        "post": "value/wnd[0]/usr/ctxtEN_EBELN-LOW",
                        "content": f"{self.task.number_45}",
                        "logic": "ignore"
                    }
                ]
            )

            response = self.send_template_request(
                json=[
                    {"content": f"{self.task.number_45}", "post": "value/wnd[0]/usr/ctxtEN_EBELN-LOW"},
                    {"post": "action/304/wnd[0]/usr/ctxtEN_EBELN-LOW", "content": "position=10", "logic": "ignore"},
                    {"post": "focus/wnd[0]/usr/ctxtEN_EBELN-LOW", "logic": "ignore"},
                    {"post": "action/3/wnd[0]/tbar[1]/btn[8]"},
                    {"get": "state/ur"}
                ]
            )

            soup = BeautifulSoup(response[4]['content'], 'lxml')
            r = re.findall(r'''grid#[\s\S]{1,10}#0,(\d{1,3})"[\s\S]{1,25}?'завод',''', response[4]['content'], flags=re.IGNORECASE)
            if len(r) != 0:
                idx = r[0]
            else:
                log.error(f'Этап 4. Поле Завод не найдено')
                logger.set_log(self.task.number_45, 'SAP S4', 'stage4', 'get_factory', 'Error', 'Получение значения завода', f'Поле Завод не найдено')
                self.task.status = '2'
                self.task.comment = 'Поле Завод не найдено'
                self.send_template_request(json=[{"post": "action/3/wnd[0]/tbar[0]/btn[15]"}, {"get": "state/ur"}])
                return self.task

            self.task.factory = soup.find('span', id=re.compile(f'grid#.+#1,{idx}#if')).text
            log.info(f'Этап 4. Завод = {self.task.factory}')
            logger.set_log(self.task.number_45, 'SAP S4', 'stage4', 'get_factory', 'OK', 'Получение значения завода',f'Завод = {self.task.factory}')
            self.send_template_request(json=[{"post": "action/3/wnd[0]/tbar[0]/btn[15]"}, {"get": "state/ur"}])
        else:
            log.warning(f'Этап 4. Тип поставки не равен 1. Тип поставки = {self.task.delivery_type}.')
            logger.set_log(self.task.number_45, 'SAP S4', 'stage4', 'get_factory', 'Warning', 'Получение значения завода',f'Тип поставки не равен 1. Тип поставки = {self.task.delivery_type}.')

        self.send_template_request(json=[{"post": "action/3/wnd[0]/tbar[0]/btn[15]"}, {"get": "state/ur"}])
        log.info('Этап 4. Конец.')
        logger.set_log(self.task.number_45, 'SAP S4', 'stage4', 'get_factory', 'Info', 'Получение значения завода','Завершено')
        return self.task

    @log.write_by_method
    def __clear_form(self):
        """Очищает все поля от кешированных данных"""

        self.send_template_request(
            json=[
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_EKORG-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_EBELN-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_EKORG-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_MFRPN-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtSELPA-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_BSART-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_EKGRP-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_WERKS-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_PSTYP-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_KNTTP-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_EINDT-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtP_GULDT"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtP_RWEIT"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_LIFNR-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_RESWK-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_MATNR-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_MATKL-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_BEDAT-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/txtS_EAN11-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/txtS_IDNLF-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_LTSNR-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_AKTNR-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_SAISO-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/txtS_SAISJ-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/txtP_TXZ01"},
                {"content": "", "post": "value/wnd[0]/usr/txtP_NAME1"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_EBELN-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_EKORG-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_MFRPN-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtSELPA-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_BSART-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_EKGRP-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_WERKS-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_PSTYP-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_KNTTP-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_EINDT-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_LIFNR-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_RESWK-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_MATNR-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_MATKL-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_BEDAT-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/txtS_EAN11-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/txtS_IDNLF-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_LTSNR-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_AKTNR-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtS_SAISO-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/txtS_SAISJ-HIGH"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_EBELN-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_EKORG-LOW"},
                {"content": "", "post": "value/wnd[0]/usr/ctxtEN_MFRPN-LOW"},
            ]
        )
