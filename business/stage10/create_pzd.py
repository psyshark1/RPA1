import math
import unicodedata, re, sap_web.utils
from html import unescape
from bs4 import BeautifulSoup as bs4, CData
from datetime import datetime
from requests import Response, Session
from logger import log
from sap_web import WebGuiBase, HttpData, HttpMethod, SapWebError

from business.check_documents_in_edo.parsers import WebGuiParser
from business.models.dto import ReflectTask, TaskDocument, TaskDeliveryVolume
from little_mailer import Mailer, MailItem

from db.logger import logger


class PreRegDocument(WebGuiBase):

    """Данный класс представляет собой Предварительно Зарегестрированный Документ (ПЗД) в SAP Web Gui"""

    def __init__(self, uuid: str, session: Session, task: ReflectTask, doc: TaskDocument):

        super().__init__(base_url='http://sap-rio.megafon.ru',session=session)

        self.uuid = uuid.replace("-", "")

        self.task = task
        self.doc = doc

        if doc.date_rule == 3:
            self.recalc_date = task.signing_date_mgf_side
        elif doc.date_rule == 4:
            self.recalc_date = task.signing_date_ka_side
        elif doc.date_rule == 2:
            self.recalc_date = doc.recalc_date_fiori
        elif doc.date_rule == 1:
            self.recalc_date = ''
        elif doc.date_rule == 5:
            self.recalc_date = ''

    @log.write_by_method
    def create(self, mail, mail_pass, mail_to)-> bool:

        transaction_string = f"*/CCPM/ITSLAUNCHER%20GV_ENTITY=PROCESS;GV_OBJCODE=ININV;GV_OKCODE=RUN;GV_RETPAR=RBN.GJR;GV_TCODE=MIR7;GV_UUID={self.uuid}"

        self.preload_page1(transaction_string)

        self.__pre_press_ok_btn(transaction_string)

        self.__press_ok_btn(transaction_string)

        self.__switch_balance_unit("MGF")

        self.__fill_basedata_tab()

        self.__fill_tax_tab()

        self.__fill_payment_tab()

        basedata = self.__select_basedata_tab()
        balance = self.parse_balance(basedata)
        table = self.parse_table(basedata)

        mailer = Mailer(mail, mail_pass)
        if self.doc.currency == "RUB":
            if 1 > balance > -1:
                self.__fill_zkz_na_post(balance+table[1])
            else:
                log.info(f'{self.task.number_45} - Создание ПЗД - Ошибка сальдо при создании 51')
                logger.set_log(f'{self.task.number_45}', 'SAP S4', 'create_pzd', 'process.create', 'Error', 'Создание ПЗД',
                               'Ошибка сальдо при создании 51')
                mailer.send_msg(MailItem(
                    to=[mail_to],
                    subject='Ошибка ЭДО RPA-1079',
                    body=f'По заданию ИД {self.task.id} №{self.task.number_45} Ошибка сальдо при создании 51',
                    sender_email=mail,
                ))

                self.task.status = '4'
                self.task.comment = self.task.comment + "Ошибка сальдо при создании 51;"

                self.__save_tmp()

                return False

        else:
            if balance == 0:
                logger.set_log(f'{self.task.number_45}', 'SAP S4', 'create_pzd', 'process.create', 'Error', 'Создание ПЗД',
                               'Ошибка сальдо при создании 51, баланс = 0')
                mailer.send_msg(MailItem(
                    to=[mail_to],
                    subject='Ошибка ЭДО RPA-1079',
                    body=f'По заданию ИД {self.task.id} №{self.task.number_45} Ошибка сальдо при создании 51',
                    # тело сообщения
                    sender_email=mail,
                ))

                self.task.status = '4'
                self.task.comment = self.task.comment + "Ошибка сальдо при создании 51;"

                self.__save_tmp()

                return False

        if self.task.delivery_type == 2:
            # volume_list = [vars(volume) for volume in self.task.volume_list]
            #
            # sort_by_doc = lambda a: a["buy_document"] and a['pos_prd_doc']
            # pairs = zip(sorted(volume_list, key=sort_by_doc), sorted(table, key=sort_by_doc))
            # if_different = any(x != y for x, y in pairs)

            not_founded_elements = tuple(filter(lambda x: {"buy_document": x.buy_document, "pos_prd_doc": x.pos_prd_doc} not in table[0], self.task.volume_list))

            if len(self.task.volume_list) > len(table[0]) or not_founded_elements:
                logger.set_log(f'{self.task.number_45}', 'SAP S4', 'create_pzd', 'process.create', 'Error', 'Создание ПЗД',
                               'Ошибка сальдо при создании 51, не все документы подтянуты')
                mailer.send_msg(MailItem(
                    to=[mail_to],
                    subject='Ошибка ЭДО RPA-1079',
                    body=f'По заданию ИД {self.task.id} №{self.task.number_45} Ошибка создания ПЗД, не все документы подтянуты',
                    sender_email=mail,
                ))
                self.task.status = '4'
                self.task.comment = self.task.comment + "Ошибка создания ПЗД, не все документы подтянуты;"
                return False

        self.__save()
        return True

    def __fill_basedata_tab(self):

        """Заполнить вкладку Баз.данные"""

        self.__select_basedata_tab()

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                ## У всех "logic": "ignore" removed
                # Операция "Счет"
                {"content":"1","post":"value/wnd[0]/usr/cmbRM08M-VORGANG"},
                # Дата счёта
                {
                    "content": f"{self.doc.upd_date}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TOTAL/ssubHEADER_SCREEN:SAPLFDCB:0010/ctxtINVFO-BLDAT"
                },
                # Дата проводки
                {
                    "content": f"{self.task.processing_date}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TOTAL/ssubHEADER_SCREEN:SAPLFDCB:0010/ctxtINVFO-BUDAT"
                },
                # Сумма
                {
                    "content": f"{str(self.doc.summa_with_nds).replace('.',',')}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TOTAL/ssubHEADER_SCREEN:SAPLFDCB:0010/txtINVFO-WRBTR"
                },
                # Валюта
                {
                    "content": f"{self.doc.currency}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TOTAL/ssubHEADER_SCREEN:SAPLFDCB:0010/ctxtINVFO-WAERS"
                },
                # Дата пересчёта
                {
                    "content": f"{self.recalc_date}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TOTAL/ssubHEADER_SCREEN:SAPLFDCB:0010/subSUBBAS04:SAPLZMM_E03E_0014:9100/ctxtZZWWERT"
                },

                ## Ссылка на ЗкзНаПост
                {"post":"action/4/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005/subITEMS:SAPLMR1M:6011/tabsITEMTAB/tabpITEMS_PO"},

                # Тип ссылочного документа
                {
                    "content": "1",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/subITEMS:SAPLMR1M:6011/tabsITEMTAB/tabpITEMS_PO/ssubTABS:SAPLMR1M:6020/cmbRM08M-REFERENZBELEGTYP"
                },
                # Номер документа закупки
                {
                    "content": f"{self.task.number_45}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/subITEMS:SAPLMR1M:6011/tabsITEMTAB/tabpITEMS_PO/ssubTABS:SAPLMR1M:6020"
                            "/subREFERENZBELEG:SAPLMR1M:6211/ctxtRM08M-EBELN"
                },
                {"post":"action/304/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005/subITEMS:SAPLMR1M:6011/tabsITEMTAB/tabpITEMS_PO/ssubTABS:SAPLMR1M:6020/subREFERENZBELEG:SAPLMR1M:6211/ctxtRM08M-EBELN","content":"position=10"},
                {"post":"focus/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005/subITEMS:SAPLMR1M:6011/tabsITEMTAB/tabpITEMS_PO/ssubTABS:SAPLMR1M:6020/subREFERENZBELEG:SAPLMR1M:6211/ctxtRM08M-EBELN"},
                {"post":"vkey/0/ses[0]"},
                {"get": "state/ur"}
            ]
        )

        res = self.send_request(http_data)

        if self.__bad_messagebar_check(res,http_data):
            xx=1

    def __fill_tax_tab(self):

        """Заполнить вкладку Налог"""

        self.__select_tax_tab()

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                # Налог в валюте
                {
                    "content": f"{str(self.doc.summa_nds).replace('.',',')}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TAX/ssubHEADER_SCREEN:SAPLTAX1:0501"
                            "/tblSAPLTAX1STEUER_CTRL/txtRTAX1U12-FWSTE[1,0]"
                },
                # БазаНалог
                {
                    "content": f"{str(self.doc.document_sum).replace('.',',')}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TAX/ssubHEADER_SCREEN:SAPLTAX1:0501"
                            "/tblSAPLTAX1STEUER_CTRL/txtRTAX1U12-FWBAS[2,0]"
                },
                # Код налога
                # {
                #     "content": "CI",
                #     "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                #             "/tabsHEADER/tabpHEADER_TAX/ssubHEADER_SCREEN:SAPLTAX1:0501"
                #             "/tblSAPLTAX1STEUER_CTRL/cmbRTAX1U12-MWSKZ[3,0]"
                # },
                {"get": "state/ur"}
            ]
        )

        res = self.send_request(http_data)
        if self.__bad_messagebar_check(res,http_data):
            xx=1


    def __fill_payment_tab(self):

        """Заполнить вкладку Платёж"""

        self.__select_payment_tab()

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                # Баз. дата
                {
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_PAY/ssubHEADER_SCREEN:SAPLFDCB:0020/ctxtINVFO-ZFBDT",
                    "content": f"{datetime.now().strftime('%d.%m.%Y')}",
                },
                {"get": "state/ur"}
            ]
        )

        res = self.send_request(http_data)
        if self.__bad_messagebar_check(res, http_data):
            xx = 1

    def __fill_zkz_na_post(self, summa):

        """Заполнить ЗкзНаПост"""

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {
                    "content": f"{summa}",
                    "post": "value/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/subITEMS:SAPLMR1M:6011/tabsITEMTAB/tabpITEMS_PO/ssubTABS:SAPLMR1M:6020"
                            "/subITEM:SAPLMR1M:6310/tblSAPLMR1MTC_MR1M/txtDRSEG-WRBTR[1,0]"
                },
                {"get": "state/ur"}
            ]
        )

        res = self.send_request(http_data)
        if self.__bad_messagebar_check(res,http_data):
            xx=1

    def __save(self):

        """Кнопка Сохранить Предварительно Зарегистриорванный Документ"""

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {
                    "post": "action/3/wnd[0]/tbar[0]/btn[11]"
                }
            ]
        )

        res = self.send_request(http_data)
        if self.__bad_messagebar_check(res, http_data):
            xx = 1

    def __save_tmp(self):

        """Кнопка Сохранить временно"""

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {
                    "post": "action/3/wnd[0]/tbar[1]/btn[5]"
                }
            ]
        )

        self.send_request(http_data)

    @staticmethod
    def parse_balance(res: Response) -> float:

        """Парсинг значения сальдо"""

        content = next(i for i in res.json() if "content" in i)["content"]
        tree = bs4(content, "html.parser")
        content = tree.find(id='webguiPage0').find(text=lambda tag: isinstance(tag, CData)).string
        formatted_content = unicodedata.normalize('NFKC', unescape(content))
        tree = bs4(formatted_content, "html.parser")
        balance = tree.find(title='Сальдо документа')["value"]
        balance = float(balance.replace(" ", "").replace(",", "."))

        return balance

    #@staticmethod
    def parse_table(self, resp: Response) -> tuple:

        """Парсинг значения суммы первой табличной записи ЗкзНаПост"""

        '''content = next(i for i in res.json() if "content" in i)["content"]
        tree = bs4(content, "html.parser")
        content = tree.find(id='webguiPage0').find(text=lambda tag: isinstance(tag, CData)).string
        formatted_content = unicodedata.normalize('NFKC', unescape(content))
        tree = bs4(formatted_content, "html.parser")
        # summa = tree.find("span", {"name": re.compile(r'tbl\d{3,5}\[1,2]_c')})
        # summa = float(content.replace(" ", "").replace(",", "."))
        i = 1
        table = []
        table_row = lambda i: tree.find_all("span", {"name": re.compile('tbl\d{{3,5}}\[{},\d]_c'.format(i))})
        while table_row(i):
            row = [tag.text for tag in table_row(i)]
            table.append({"pos_prd_doc": row[0], "summa": row[1], "buy_document": row[4]})
            i+=1'''
        r = re.findall(r"id:'M0:46:1:6:1:2B258:2:1'[\s\S]+?lastVisibleRow:(\d{1,3})[\s\S]+?rowCount:(\d{1,3})", resp.text, flags=re.IGNORECASE)
        if len(r) != 0:
            visible_rowcount = int(r[0][0])
            table_rowcount = int(r[0][1])
        else:
            err=1

        summ = 0.0
        volume_list = []
        checked_rowcount = visible_rowcount

        while checked_rowcount <= table_rowcount + visible_rowcount:
            r = re.findall(r"tbl\d{1,5}\[\d{1,3},(?:6|7)\][\s\S]{1,30}?lsdata[\s\S]{1,30}?FREETEXT',4:'([\s\S]{0,50}?)'",resp.text, flags=re.IGNORECASE)

            positions = r[1::2]
            contracts = r[0::2]
            values = []

            for i in range(0, int(len(positions))):
                values.append(dict(buy_document=contracts[i], pos_prd_doc=positions[i]))

            volume_list += values

            if summ == 0.0:
                r = re.findall(r"tbl\d{1,5}\[\d{1,3},2\][\s\S]{1,30}?lsdata[\s\S]{1,30}?FREETEXT'(?:[\s\S]{1,90}?|),4:'([\s\S]{0,50}?)'",resp.text, flags=re.IGNORECASE)
                if len(r) != 0:
                    summ = float(r[0].replace('x', '').replace('\\', '').replace(',', '.'))
                    if len(str(summ).split(".")[1]) > 2:
                        summ = math.floor(summ * 100) / 100

            resp = self.__scroll_table(checked_rowcount)
            checked_rowcount += visible_rowcount

        # M0:46:1:6:1:2B258:2:1-mrss-hdr-left-content -- left header
        # M0:46:1:6:1:2B258:2:1-mrss-hdr-none-content -- right header
        # M0:46:1:6:1:2B258:2:1-mrss-cont-left-content -- left content
        # M0:46:1:6:1:2B258:2:1-mrss-cont-none-content -- right content

        return (volume_list, summ)

    def __pre_press_ok_btn(self, transaction) -> str:
        """
        Выполняет запрос нажатия 'ОК'.
        Возвращает текст ответа, в котором содержиться url для последующих запросов.
        """
        http_data = HttpData(
            method=HttpMethod.GET,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
                'SEC_SESSTOKEN': self._ses_token,
                '~path': f'/{self._path}',
                '~transaction': transaction
            }
        )

        resp = self.send_request(http_data)
        return resp.text

    def __press_ok_btn(self, transaction) -> str:
        """
        Выполняет запрос нажатия 'ОК'.
        Возвращает текст ответа, в котором содержиться url для последующих запросов.
        """
        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
                'SEC_SESSTOKEN': self._ses_token,
                '~path': f'/{self._path}',
                '~transaction': transaction
            },
            json=[
                {'post': 'okcode/ses[0]', 'content': 'OK'},
                {'post': 'vkey/0/ses[0]'},
                {'get': 'state/ur'}
            ]
        )

        resp = self.send_request(http_data)
        return resp.text

    def __switch_balance_unit(self, unit: str):

        """Переключить балансовую единицу"""

        self.__balance_unit_window_open()

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {
                    "content": f"{unit.upper()}",
                    "post": "value/wnd[1]/usr/ctxtBKPF-BUKRS"
                },
                {"post": "vkey/0/ses[0]"}, {"get": "state/ur"}]

        )
        self.send_request(http_data)

    def __balance_unit_window_open(self):

        """Открыть окно переключения балансовой единицы"""

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {"post": "vkey/7/wnd[0]"},
                {"get": "state/ur"}
            ]

        )
        self.send_request(http_data)


    def __select_basedata_tab(self) -> Response:

        """
        Нажать вкладку Баз.данные
        Возвращает Response в котором содержится html вкладки
        """

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {
                    "post": "action/4/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TOTAL"
                },
                {"get": "state/ur"}
            ]
        )

        return self.send_request(http_data)

    def __select_payment_tab(self) -> Response:

        """
        Нажать вкладку Платёж
        Возвращает Response в котором содержится html вкладки
        """

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {
                    "post": "action/4/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_PAY"
                },
                {"get": "state/ur"}

            ]
        )

        return self.send_request(http_data)

    def __select_tax_tab(self) -> Response:

        """
        Нажать вкладку Налог
        Возвращает Response в котором содержится html вкладки
        """

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                {
                    "post": "action/4/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005"
                            "/tabsHEADER/tabpHEADER_TAX"
                },
                {"get": "state/ur"}

            ]
        )

        return self.send_request(http_data)

    def preload_page1(self, transaction: str = None):
        """
        Выполняет предварительную загрузку запрашиваемой страницы.
        Обязательно вызывать перед открытием главной страницы или после перехода из SAP Fiori к конкретной транзакции.

        :param transaction: (опционально) строка транзакции из url-адреса (в случае перехода на страницу из SAP Fiori)
        :return:
        """
        self.__set_token_and_path1(transaction)

        http_data = HttpData(
            method=HttpMethod.POST,
            url=self._path,
            data={
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
                'SEC_SESSTOKEN': self._ses_token,
                '~path': f'/{self._path}',
                'SAPURClientInspector': 'load',
                '~transaction': transaction,
                '~webguiUserAreaHeight':2003,
                '~webguiUserAreaWidth':3920,
                '~webguiScreenHeight':2160,
                '~webguiScreenWidth':4096,
                'ThemedRasterHeight':16,
                'ThemedRasterWidth':6,
                'ThemedAbapListRasterHeight':14,
                'ThemedAbapListRasterWidth':5,
                'ThemedTableRowHeight':16,
                'ThemedScrollbarDimension':12,
                '~ci_result': '~webguiUserAreaHeight=2003;~webguiUserAreaWidth=3920;~webguiScreenWidth=4096;~webguiScreenHeight=2160;ThemedScrollbarDimension=12'
            }
        )

        self.send_request(http_data)

    def __set_token_and_path1(self, transaction: str = None):
        """
        Устанавливает значения параметров SEC_SESSTOKEN и path

        :param transaction:
        :return:
        """

        http_data = HttpData(
            method=HttpMethod.GET,
            url=f'sap/bc/gui/sap/its/webgui?sap-client=800&sap-language=RU&~transaction={transaction}',
            params={
                'sap-client': self.CLIENT,
                'sap-language': self.LANGUAGE,
                '~transaction': transaction,
                '~webguiUserAreaHeight':2003,
                '~webguiUserAreaWidth':3920,
                '~webguiScreenHeight':2160,
                '~webguiScreenWidth':4096,
                'ThemedRasterHeight':16,
                'ThemedRasterWidth':6,
                'ThemedAbapListRasterHeight':14,
                'ThemedAbapListRasterWidth':5,
                'ThemedTableRowHeight':16,
                'ThemedScrollbarDimension':12,
                '~ci_result': '~webguiUserAreaHeight=2003;~webguiUserAreaWidth=3920;~webguiScreenWidth=4096;~webguiScreenHeight=2160;ThemedScrollbarDimension=12'
            }
        )

        resp = self.send_request(http_data)

        ses_token = sap_web.utils.parse_between('name="~SEC_SESSTOKEN"        value="', '" />', resp.text)
        path = sap_web.utils.parse_between(start='<form id="webguiStartForm" name="webguiStartForm" method="post" action="',
                             stop='" target="', text=resp.text)

        if not ses_token or not path:
            raise SapWebError('Error getting parameters "SEC_SESSTOKEN" and "path"')

        self._ses_token = ses_token
        self._path = path[1:]

    def __scroll_table(self, scroll_pos):

        """Скроллинг таблицы поставок"""

        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'true',
                '~SEC_SESSTOKEN': self._ses_token,
            },
            json=[
                # Баз. дата
                {
                    "post": "action/61/wnd[0]/usr/subHEADER_AND_ITEMS:SAPLMR1M:6005/subITEMS:SAPLMR1M:6011/tabsITEMTAB/tabpITEMS_PO/ssubTABS:SAPLMR1M:6020/subITEM:SAPLMR1M:6310/tblSAPLMR1MTC_MR1M",
                    "content": f"position={str(scroll_pos)}"
                },
                {"get": "state/ur"}
            ]
        )

        res = self.send_request(http_data)
        if self.__bad_messagebar_check(res, http_data):
            xx = 1
        return res

    def __messagebar_check(self, wrong_type:str, response)-> bool:
        if re.search(r"\{modalNo:'0'[\s\S]{1,250}?image--" + wrong_type, response.text, flags=re.IGNORECASE) is not None:
            return True
        return False

    def __bad_messagebar_check(self, response, http_data)-> bool:
        while self.__messagebar_check('Warning', response):
            http_data.json = [{'post': 'vkey/0/ses[0]'}, {'get': 'state/ur'}]
            response = self.send_request(http_data)

        return self.__messagebar_check('Error', response)

    def __get_messagebar_text(self, response)-> str:
        unicode_check = re.search(r'\\u', response.text, flags=re.IGNORECASE)
        msg_txt = re.findall(r"""Type:'MESSAGEBAR',applicationText:'([\s\S]+?)'""", response.text, flags=re.IGNORECASE)
        if unicode_check:
            return f'{msg_txt[0].encode("utf-8").decode("unicode-escape")}'
        else:
            return f'{msg_txt[0]}'

class ReflectTaskProcessor:

    def __init__(self, uuid, session: Session, task: ReflectTask, mail, mail_pass, mail_to):

        self.uuid = uuid
        self.session = session
        self.task = task
        self.mail = mail
        self.mail_pass = mail_pass
        self.mail_to = mail_to
        #self.path = path
        #self.ses_token = ses_token

    def process(self):
        logger.set_log(f'{self.task.number_45}', 'Python', 'create_pzd', 'process', 'Info', 'Создание ПЗД', 'Начало работы')
        pzd = PreRegDocument(self.uuid, self.session, self.task, self.task.document)
        r = pzd.create(self.mail, self.mail_pass, self.mail_to)
        logger.set_log(f'{self.task.number_45}', 'Python', 'create_pzd', 'process', 'Info', 'Создание ПЗД','Завершение работы')
        return r
