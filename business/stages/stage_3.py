import re
from datetime import datetime

from logger import log
from bs4 import BeautifulSoup

from business.models.dto import ReflectTask
from business.models.sap_web_additions import BaseAdditions
from db.logger import logger
from mail.OWA_MailSender import OWA_MailSender
from config import ENV_DATA, USER_EMAIL, EMAIL_SENDER



class Stage3(BaseAdditions):
    """Этап 3. Получить данные для проверки создания 18* полная поставка (вх. поставка ZPURDOCS)"""

    def __init__(self, mail_sender: OWA_MailSender, task: ReflectTask, session=None):
        """
        Конструктор

        :param task: Задание
        :param session: (Опционально) Объект сесии
        """

        #log.add(dir_path=f'log_{datetime.now().strftime("%d-%m-%Y_%H-%M-%S")}.log', level='DEBUG')

        super(Stage3, self).__init__(session=session)

        self.task = task
        self.mail_sender = mail_sender

        if not session:
            self.login(ENV_DATA['sap_gui_login'], ENV_DATA['sap_gui_pass'])
        self.open_home_page()

    @log.write_by_method
    def get_data_18(self):
        """Открывает транзакцию ZPURDOCS и получает данные 18*"""

        log.info('Этап 3. Запуск.')

        # Открытие транзакции

        self.open_transaction('ZPURDOCS')
        log.info('Этап 3. Открытие транзакции ZPURDOCS.')
        logger.set_log(self.task.number_45, 'SAP S4', 'stage3', 'get_data_18', 'Info', 'Получить данные для проверки создания 18* полная поставка','Открытие транзакции ZPURDOCS')

        self.__clear_form()

        response = self.send_template_request(
            json=[
                {'content': '', 'post': 'value/wnd[0]/usr/ctxtS_ORDER-LOW'},
                {'content': 'ZNB', 'post': 'value/wnd[0]/usr/ctxtS_ORDER-LOW'},
                {'content': '/F1_PD_AVV', 'post': 'value/wnd[0]/usr/txtP_VAR'},
                #{'content': 'RPA-1079', 'post': 'value/wnd[0]/usr/txtP_VAR'},
                {'content': f'{self.task.number_45}', 'post': 'value/wnd[0]/usr/ctxtS_EBELN-LOW'},
                {'content': '', 'post': 'value/wnd[0]/usr/ctxtS_EBELN-LOW'},
                {'content': f'{self.task.number_45}', 'post': 'value/wnd[0]/usr/ctxtS_EBELN-LOW'},
                {'post': 'action/304/wnd[0]/usr/ctxtS_EBELN-LOW', 'content': f'position={len(self.task.number_45)}', 'logic': 'ignore'},
                {'post': 'focus/wnd[0]/usr/ctxtS_EBELN-LOW', 'logic': 'ignore'},
                {'post': 'action/3/wnd[0]/tbar[1]/btn[8]'},
                {'get': 'state/ur'}
            ]
        )

        date_difference = self.task.delivery_date.date() - datetime.now().date()

        dynamic_number = re.search('grid#.+#1,8#if', response[9]['content'])[0][5:]
        dynamic_number = dynamic_number[:dynamic_number.index('#')]

        material_document_col = re.findall(r'grid#'+dynamic_number+'#0,(\d{1,2})#cp[\s\S]{1,150}?докуммтр', response[9]['content'], flags=re.IGNORECASE)[0]
        signing_date_mgf_side_col = re.findall(r'grid#'+dynamic_number+'#0,(\d{1,2})#cp[\s\S]{1,150}?датаподпмф', response[9]['content'], flags=re.IGNORECASE)[0]
        signing_date_ka_side_col = re.findall(r'grid#'+dynamic_number+'#0,(\d{1,2})#cp[\s\S]{1,150}?датаподпка', response[9]['content'], flags=re.IGNORECASE)[0]
        contract_number_col = re.findall(r'grid#'+dynamic_number+'#0,(\d{1,2})#cp[\s\S]{1,150}?долгосрочный', response[9]['content'], flags=re.IGNORECASE)[0]
        name_ka_col = re.findall(r'grid#'+dynamic_number+'#0,(\d{1,2})#cp[\s\S]{1,150}?имяпланов', response[9]['content'], flags=re.IGNORECASE)[0]

        soup = BeautifulSoup(str(response[9]['content']), 'lxml')
        material_document = soup.find('span', id=f'grid#{dynamic_number}#1,{material_document_col}#if-r')

        if self.task.number_18 != '' and self.task.delivery_type == 1:
            log.info('Этап 3. Номер 18 = не пусто и тип поставки = 1.')

            self.task.number_50 = material_document.text
            log.info(f'Этап 3. Номер 50 = {self.task.number_50}')

            if date_difference.days == 4:

                log.error(f'Этап 3. Ошибка ЭДО: Задание {self.task.id} № {self.task.number_45} - 50* просрочен.')
                logger.set_log(self.task.number_45, 'SAP S4', 'stage3', 'get_data_18', 'Error','Получить данные для проверки создания 18* полная поставка', '50* просрочен')
                self.mail_sender.send_mail(EMAIL_SENDER, USER_EMAIL, 'Ошибка ЭДО RPA-1079', f'По заданию ИД {self.task.id} № {self.task.number_45} Просрочен 50.')

                self.task.comment = self.task.comment + 'Просрочен 50;'
                self.task.status = '4'
                self.send_template_request(json=[{"post": "action/3/wnd[0]/tbar[0]/btn[15]"}, {"get": "state/ur"}])
                return 12
            else:
                if material_document.text == '':
                    log.error(f'Этап 3. Ошибка ЭДО: Задание {self.task.id} № {self.task.number_45} - 50* не создан.')
                    logger.set_log(self.task.number_45, 'SAP S4', 'stage3', 'get_data_18', 'Error', 'Получить данные для проверки создания 18* полная поставка', '50* не создан')
                    self.mail_sender.send_mail(EMAIL_SENDER, USER_EMAIL, 'Ошибка ЭДО RPA-1079', f'По заданию ИД {self.task.id} № {self.task.number_45} Не создан 50.')

                    self.task.comment = self.task.comment + 'Не создан 50;'
                    self.task.status = '2'
                    self.send_template_request(json=[{"post": "action/3/wnd[0]/tbar[0]/btn[15]"}, {"get": "state/ur"}])
                    return 12

        if self.task.number_18 == '' and self.task.delivery_type == 1:
            log.info('Этап 3. Номер 18 = пусто и тип поставки = 1.')

            self.task.line_count = material_document.find_parent('tbody')['irowsfragmentlength']
            self.task.name_ka = soup.find('span', id=f'grid#{dynamic_number}#1,{name_ka_col}#if').text

            log.info(
                f'\tКол-во строк = {self.task.line_count}\n'
                f'\tНаименование KA = {self.task.name_ka}\n'
            )

        self.task.signing_date_mgf_side = soup.find('span', id=f'grid#{dynamic_number}#1,{signing_date_mgf_side_col}#if').text
        self.task.signing_date_ka_side = soup.find('span', id=f'grid#{dynamic_number}#1,{signing_date_ka_side_col}#if').text
        self.task.contract_number = soup.find('span', id=f'grid#{dynamic_number}#1,{contract_number_col}#if').text

        log.info('\n'
            f'\tДата подписание со стороны МФ = {self.task.signing_date_mgf_side}\n'
            f'\tДата подписания со стороны KA = {self.task.signing_date_ka_side}\n'
            f'\tНомер договора = {self.task.contract_number}'
        )

        if self.task.number_18 == '':
            log.info('Этап 3. Конец.')
            self.send_template_request(json=[{"post": "action/3/wnd[0]/tbar[0]/btn[15]"}, {"get": "state/ur"}])
            return 7

        log.info('Этап 3. Конец.')
        logger.set_log(self.task.number_45, 'SAP S4', 'stage3', 'get_data_18', 'OK','Получить данные для проверки создания 18* полная поставка','Полуен номер договора')
        self.send_template_request(json=[{"post":"action/3/wnd[0]/tbar[0]/btn[15]"},{"get":"state/ur"}])
        return 0

    @log.write_by_method
    def __clear_form(self):
        """Очищает все поля от кешированных данных"""

        template = [
            'ctxtS_ORDER-LOW', 'ctxtS_EBELN-LOW', 'ctxtS_EBELP-LOW', 'ctxtS_LIFNR-LOW', 'ctxtS_EKORG-LOW',
            'ctxtS_EKGRP-LOW', 'ctxtS_BUKRS-LOW', 'ctxtS_ERNAM-LOW', 'ctxtS_BEDAT-LOW', 'ctxtS_AEDAT-LOW',
            'ctxtS_KONNR-LOW', 'ctxtS_KTPNR-LOW', 'ctxtS_BSART-LOW', 'ctxtS_BANFN-LOW', 'ctxtS_BNFPO-LOW',
            'ctxtS_MATKL-LOW', 'ctxtS_MATNR-LOW', 'ctxtS_WERKS-LOW', 'ctxtS_LFDAT-LOW', 'ctxtS_ELIKZ-LOW',
            'ctxtS_COMPL-LOW', 'ctxtS_BUMKPF-LOW', 'ctxtS_BURBKP-LOW', 'ctxtS_ORDER-HIGH', 'ctxtS_EBELN-HIGH',
            'ctxtS_EBELP-HIGH', 'ctxtS_LIFNR-HIGH', 'ctxtS_EKORG-HIGH', 'ctxtS_EKGRP-HIGH', 'ctxtS_BUKRS-HIGH',
            'ctxtS_ERNAM-HIGH', 'ctxtS_BEDAT-HIGH', 'ctxtS_AEDAT-HIGH', 'ctxtS_KONNR-HIGH', 'ctxtS_KTPNR-HIGH',
            'ctxtS_BSART-HIGH', 'ctxtS_BANFN-HIGH', 'ctxtS_BNFPO-HIGH', 'ctxtS_MATKL-HIGH', 'ctxtS_MATNR-HIGH',
            'ctxtS_WERKS-HIGH', 'ctxtS_LFDAT-HIGH', 'ctxtS_BUMKPF-HIGH', 'ctxtS_BURBKP-HIGH', 'ctxtS_PSPNR-LOW',
            'ctxtS_NPLNR-LOW', 'ctxtS_PSPNR-HIGH', 'ctxtS_NPLNR-HIGH', 'txtP_VAR', 'ctxtP_EX1', 'txtP_EXT1',
            'ctxtP_EX2', 'ctxtP_EX3', 'ctxtP_EX4', 'ctxtP_FILE', 'ctxtP_EX5', 'txtP_ROWFR', 'txtP_ROWTO'
        ]

        self.send_template_request(
            json=[
                *[{'post': f'value/wnd[0]/usr/{i}', 'content': '',
                   'logic': 'ignore'} for i in template]
            ]
        )
