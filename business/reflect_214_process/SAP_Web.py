import json
import re
from datetime import datetime

import win32com.client
from sap_web import HttpData, HttpMethod
from sap_web.web_gui import WebGuiBase
from business.models.dto import ReflectTask
from logger import log
from db.logger import logger

class Sap(WebGuiBase):
    def __init__ (self, mail, m_from:str, m_to:str, SapLogin=None, SapPassword=None, session=None, path:str = None, ses_token:str = None):

        if session is None or path is None or ses_token is None:
            super().__init__('http://sap-rio.megafon.ru')
            super().login(SapLogin, SapPassword)
            super().open_home_page()
        elif session is not None and path is not None and ses_token is not None:
            super().__init__(base_url='http://sap-rio.megafon.ru',session=session)
            self._ses_token = ses_token
            self._path = path

        self.http_data = None
        self.response = None
        self.mail = mail
        self.mail_from = m_from
        self.mail_to = m_to
        self.open_home_page()

    def start_transaction(self,tr_name:str):

        self.http_data = HttpData(
            method=HttpMethod.POST,
            url=f'{self._path}/batch/json',
            params={
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'false',
                '~SEC_SESSTOKEN': self._ses_token,
                'SEC_SESSTOKEN': self._ses_token,
                '~path': f'/{self._path}',
                'webguiUserAreaHeight':2003,
                'webguiUserAreaWidth':3920,
                'webguiScreenHeight': 2160,
                'webguiScreenWidth': 4096,
                'webguiDynproMetric': 1,
                'ThemedRasterHeight':16,
                'ThemedRasterWidth':6,
                'ThemedAbapListRasterHeight':14,
                'ThemedAbapListRasterWidth':5,
                'ThemedTableRowHeight':16
            },
            json=[
                {'content': f'{tr_name}', 'post': 'okcode/ses[0]'},
                {'post': 'vkey/0/ses[0]'},
                {'get': 'state/ur'}
            ]
        )

        self.send_request(self.http_data)

    def get_214_process(self,reflect:ReflectTask)-> str:

        self.http_data.params = {
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'false',
                '~SEC_SESSTOKEN': self._ses_token
            }
        self.http_data.json = [
            {'content':'A04','post':'value/wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_FIRSTLINE:SAPLMIGO:0011/cmbGODYNPRO-ACTION'},
            {'get':'state/ur'}
            ]

        self.response = self.send_request(self.http_data)

        if self.__bad_messagebar_check_MIGO("Error"):
            log.error(f'{reflect.number_45} - Получение процесса 214* - Ошибка выбора документа материала')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'get_214_process', 'Error',
                           'Выбор документа материала', f'Ошибка выбора документа материала - {self.__get_messagebar_text()}')
            reflect.comment = reflect.comment + f'Получение процесса 214*. Ошибка выбора документа материала - {self.__get_messagebar_text()};'
            self.__exit_transact(False)
            return 'error'

        self.http_data.json = [
            {'content': f'{reflect.number_50}', 'post': 'value/wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_FIRSTLINE:SAPLMIGO:0011/subSUB_FIRSTLINE_REFDOC:SAPLMIGO:2010/txtGODYNPRO-MAT_DOC'},
            {'content': f'{datetime.now().date().strftime("%Y")}', 'post': 'value/wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_FIRSTLINE:SAPLMIGO:0011/subSUB_FIRSTLINE_REFDOC:SAPLMIGO:2010/txtGODYNPRO-DOC_YEAR'},
            {'post': 'action/4/wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_HEADER:SAPLMIGO:0101/subSUB_HEADER:SAPLMIGO:0100/tabsTS_GOHEAD/tabpOK_GOHEAD_EXT_1'},
            {'post': 'vkey/0/ses[0]'},
            {'get': 'state/ur'}
            ]

        self.response = self.send_request(self.http_data)

        if self.__bad_messagebar_check_MIGO("Error"):
            log.error(f'{reflect.number_45} - Получение процесса 214* - Ошибка поиска 50*')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'get_214_process', 'Error',
                           'Ошибка поиска 50*', f'Ошибка поиска 50* - {self.__get_messagebar_text()}')
            reflect.comment = reflect.comment + f'Получение процесса 214*. Ошибка поиска 50* - {self.__get_messagebar_text()};'
            self.__exit_transact(False)
            return 'error'

        res = re.findall(r"'(214\d{12})'", self.response.text, flags=re.IGNORECASE)

        if len(res) == 0:
            log.error(f'{reflect.number_45} - Получение процесса 214* - Ошибка поиска 214* - 214* процесс отсутствует')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'get_214_process', 'Error',
                           'Ошибка поиска 214*', '214* процесс отсутствует')
            self.mail.send_mail(self.mail_from,self.mail_to,'Ошибка ЭДО RPA-1079',f'По заданию ИД {reflect.id} № {reflect.number_45} 214* процесс отсутствует')
            reflect.status = '2'
            reflect.comment = reflect.comment + 'Получение процесса 214*. 214* процесс отсутствует;'
            self.__exit_transact(False)
            return 'error'

        reflect.number_214 = res[0]

        self.http_data.json = [
            {'post': 'action/4/wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_HEADER:SAPLMIGO:0101/subSUB_HEADER:SAPLMIGO:0100/tabsTS_GOHEAD/tabpOK_GOHEAD_GENERAL'},
            {'get': 'state/ur'}
            ]

        self.response = self.send_request(self.http_data)

        res = re.findall(r'\\u043F\\u0440\\u043E\\u0432\\u043E\\u0434\\u043A\\u0438[\s\S]{1,500}value=\\"(\S{10})\\"', self.response.text, flags=re.IGNORECASE)

        if len(res) == 0:
            log.error(f'{reflect.number_45} - Получение процесса 214* - Не найдена дата проводки')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'get_214_process', 'Error',
                           'Ошибка поиска даты проводки', 'Не найдена дата проводки')
            reflect.status = '2'
            reflect.comment = reflect.comment + 'Получение процесса 214*. Не найдена дата проводки;'
            self.__exit_transact(False)
            return 'error'

        reflect.processing_date = res[0]

        self.http_data.json = [
            {'post': 'action/4/wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_HEADER:SAPLMIGO:0101/subSUB_HEADER:SAPLMIGO:0100/tabsTS_GOHEAD/tabpOK_GOHEAD_EXT_1'},
            {"post": "action/3/wnd[0]/usr/ssubSUB_MAIN_CARRIER:SAPLMIGO:0003/subSUB_HEADER:SAPLMIGO:0101/subSUB_HEADER:SAPLMIGO:0100/tabsTS_GOHEAD/tabpOK_GOHEAD_EXT_1/ssubSUB_TS_GOHEAD_EXT_1:ZMM_E03E_0013_MGNHNC:9100/btnZZPROCESSID"},
            {'get': 'state/ur'}
            ]

        self.response = self.send_request(self.http_data)

        res = re.findall(r"ProcessUUID=guid\\\\'(\S+?)\\", self.response.text, flags=re.IGNORECASE)

        if len(res) == 0:
            log.error(f'{reflect.number_45} - Получение процесса 214* - Не найден guid процесса {reflect.number_214}')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'get_214_process', 'Error',
                           'Ошибка поиска guid процесса', f'Не найден guid процесса {reflect.number_214}')
            self.__exit_transact(False)
            return 'error'

        return res[0]

    def get_inbound_supply_doc(self,reflect:ReflectTask)->int:

        self.http_data.params = {
                '~RG_WEBGUI': 'X',
                'sap-statistics': 'false',
                '~SEC_SESSTOKEN': self._ses_token
            }
        self.http_data.json = [
            {'content': f'{reflect.number_45}', 'post': 'value/wnd[0]/usr/txtLV50C-BSTNR'},
            {'post': 'vkey/0/ses[0]'},
            {'get': 'state/ur'}
            ]

        self.response = self.send_request(self.http_data)

        if re.search(r"s_s_ledr", self.response.text, flags=re.IGNORECASE):
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Ошибка статуса документа')
            logger.set_log('', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc', 'Error',
                           'Проверка 45*', 'Ошибка статуса проверки документа')
            reflect.comment = reflect.comment + 'Создание документа входящей поставки. Ошибка статуса проверки документа;'
            self.__exit_transact(True)
            return 12

        if self.__bad_messagebar_check():
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Ошибка документа')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc', 'Error', 'Проверка 45*',
                           'Ошибка проверки документа')
            reflect.comment = reflect.comment + 'Создание документа входящей поставки. Ошибка проверки документа;'
            self.__exit_transact(True)
            return 12

        res = re.findall(r"\{0:'FREETEXT',4:'"+ reflect.number_45 +"'", self.response.text, flags=re.IGNORECASE)

        if len(res) == 0:
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Не найдены процессы 45*')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc',
                           'Error', 'Проверка 45*', 'Не найдены процессы 45*')
            reflect.comment = reflect.comment + 'Создание документа входящей поставки. Не найдены процессы 45* в SAP;'
            self.__exit_transact(True)
            return 12

        row_result = len(res)

        res = re.findall(r"""id=\\"tbl\d{1,5}\[\d{1,5},25\][\s\S]{1,50}?FREETEXT[\s\S]{1,50}?,4:'\S{4}'""", self.response.text, flags=re.IGNORECASE)

        if row_result != len(res):
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Отсутствует склад')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc',
                           'Error', 'Проверка 45*', 'Отсутствует склад')
            self.mail.send_mail(self.mail_from, self.mail_to,'Ошибка ЭДО RPA-1079',f'По заданию ИД {reflect.id} № {reflect.number_45} отсутствует склад')
            reflect.status = '2'
            reflect.comment = reflect.comment + 'отсутствует склад;'
            self.__exit_transact(True)
            return 12
        if str(row_result) != reflect.line_count:
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Количествово позиций в 18* не соответствует количеству позиций в 45*')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc',
                           'Error', 'Проверка 45*', 'Количествово позиций в 18* не соответствует количеству позиций в 45*')
            self.mail.send_mail(self.mail_from, self.mail_to, 'Ошибка ЭДО RPA-1079', f'По заданию ИД {reflect.id} №{reflect.number_45} Количествово позиций в 18* не соответствует количеству позиций в 45*')
            reflect.status = '2'
            reflect.comment = reflect.comment + 'Количествово позиций в 18* не соответствует количеству позиций в 45*;'
            self.__exit_transact(True)
            return 12

        self.http_data.json = [
            {'post': 'value/wnd[0]/usr/tabsTAXI_TABSTRIP_OVERVIEW/tabpT\\01/ssubSUBSCREEN_BODY:SAPMV50A:1202/ctxtRV50A-LFDAT_LA','content':f'{reflect.author}','logic':'ignore'},
            {'post': 'vkey/8/wnd[0]'},
            {'post': 'action/4/wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\06'},
            {'get': 'state/ur'}]

        self.response = self.send_request(self.http_data)

        res = re.findall(r"""\\u0421\\u043E\\u0437\\u0434\\u0430\\u043B[\s\S]{1,1500}?FREETEXT[\s\S]{1,50}?,4:'(\d{8})'""", self.response.text, flags=re.IGNORECASE)
        if len(res) == 0:
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Таб. номер создателя не найден')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc','Error', 'Создание документа входящей поставки',
                           'Таб. номер создателя не найден')
            reflect.comment = reflect.comment + 'Создание документа входящей поставки. Таб. номер создателя не найден;'
            self.__exit_transact(True)
            return 12

        creator = self.__getADInfo(res[0])

        self.http_data.json = [
            {'post': 'action/4/wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\08'},
            {'get': 'state/ur'}]

        try:
            self.response = self.send_request(self.http_data)
        except:
            self.__exit_transact(True)
            return 12

        res = re.findall(r"""\\"(TEC_cnt\d{1,2})\\",\\"messagearea""", self.response.text, flags=re.IGNORECASE)
        if len(res) == 0:
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Не найдено поле Комментарий')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc',
                           'Error', 'Создание документа входящей поставки', 'Не найдено поле Комментарий')
            reflect.comment = reflect.comment + 'Создание документа входящей поставки. Не найдено поле Комментарий;'
            self.__exit_transact(True)
            return 12

        msg = f'{reflect.number_45} {reflect.contractor.full_name} ({creator})'#.encode('unicode_escape').decode('windows-1251')
        self.http_data.data = json.dumps([
            {'post': 'action/81/wnd[0]/usr/tabsTAXI_TABSTRIP_HEAD/tabpT\\08/ssubSUBSCREEN_BODY:SAPMV50A:2120/subTEXTEDIT:SAPLV70T:2100/cntlSPLITTER_CONTAINER/shellcont/shellcont/shell/shellcont[1]/shell',
            'content': f'ctrl_id={res[0]}&text_changed=x&selection_start={str(len(msg))}&selection_end={str(len(msg))}&scroll_pos=0&ctrl_value={msg}'},
            {'post': 'action/3/wnd[0]/tbar[0]/btn[11]'},
            {'get': 'state/ur'}], ensure_ascii=False).encode('UTF-8')

        try:
            self.response = self.send_request(self.http_data)
        except:
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Ошибка сохранения комментария')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc',
                           'Error', 'Создание документа входящей поставки', 'Ошибка сохранения комментария')
            reflect.comment = reflect.comment + 'Создание документа входящей поставки. Ошибка сохранения комментария;'
            self.__exit_transact(True)
            return 12

        res = re.findall(r"""MESSAGEBAR',applicationText[\s\S]{1,200}?(\d{8,10}):""", self.response.text,flags=re.IGNORECASE)

        if len(res) == 0:
            log.error(f'{reflect.number_45} - Создание документа входящей поставки - Отсутствует информация о созданном 18*')
            logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc',
                           'Error', 'Создание документа входящей поставки', 'Отсутствует информация о созданном 18*')
            self.mail.send_mail(self.mail_from, self.mail_to, 'Ошибка ЭДО RPA-1079', f'По заданию ИД {reflect.id} №{reflect.number_45} Ошибка создания 18*. Отсутствует информация о созданном 18*')
            reflect.status = '2'
            reflect.comment = reflect.comment + 'Отсутствует информация о созданном 18*;'
            self.__exit_transact(True)
            return 12

        reflect.number_18 = res[0]

        log.info(f'{reflect.number_45} - Создание документа входящей поставки - Создан документ {res[0]}')
        logger.set_log(f'{reflect.number_45}', 'SAP', 'create_inbound_supply_doc', 'get_inbound_supply_doc', 'OK',
                       'Создание документа входящей поставки', f'Создан документ {res[0]}')

        self.__exit_transact(True)
        return 1

    def __messagebar_check(self, wrong_type:str)-> bool:
        if re.search(r"\{modalNo:'0'[\s\S]{1,250}?image--" + wrong_type, self.response.text, flags=re.IGNORECASE) is not None:
            return True
        return False

    def __bad_messagebar_check(self)-> bool:
        while self.__messagebar_check('Warning'):
            self.http_data.json = [{'post': 'vkey/0/ses[0]'}, {'get': 'state/ur'}]
            self.response = self.send_request(self.http_data)

        return self.__messagebar_check('Error')

    def __bad_messagebar_check_MIGO(self, wrong_type:str)-> bool:
        res = re.search(r"""1:'""" + wrong_type + r"""'""", self.response.text, flags=re.IGNORECASE)

        if res:
            return True
        return False

    def __get_messagebar_text(self)-> str:
        unicode_check = re.search(r'\\u', self.response.text, flags=re.IGNORECASE)
        msg_txt = re.findall(r"""Type:'MESSAGEBAR',applicationText:'([\s\S]+?)'""", self.response.text, flags=re.IGNORECASE)
        if unicode_check:
            return f'{msg_txt[0].encode("utf-8").decode("unicode-escape")}'
        else:
            return f'{msg_txt[0]}'

    def __getADInfo(self, id):
        conn = win32com.client.Dispatch("ADODB.Connection")
        conn.Provider = "ADSDSOObject"
        query = f"select Description from 'LDAP://DC=Megafon,DC=ru' where objectClass='user' and EmployeeID='{id}'"
        conn.Open("Active Directory Provider")
        rs = conn.Execute(query)
        try:
            rs[0].movefirst
        except:
            pass
        while not rs[0].EOF:
            rslt = rs[0].Fields("Description").Value[0]
            break
        conn.Close()
        return rslt

    def __exit_transact(self, confirm:bool):

        if confirm:
            self.http_data.json = [
                {'post':'action/3/wnd[0]/tbar[0]/btn[15]'},
                {'post':'action/3/wnd[1]/usr/btnSPOP-OPTION2'},
                {'get':'state/ur'}]
        else:
            self.http_data.json = [
                {'post':'action/3/wnd[0]/tbar[0]/btn[15]'},
                {'get':'state/ur'}]

        self.send_request(self.http_data)
