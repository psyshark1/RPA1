import datetime
import json
import re
from datetime import date
from pathlib import Path, WindowsPath
from typing import List

from sap_web import HttpData, HttpMethod, WebGuiBase, parse_between

from business.check_documents_in_edo.constants import NETTO_INPUT_ID, CURRENCY_INPUT_ID, VERSION_HEADER_L_ID, VERSION_HEADER_R_ID, VERSION_BODY_R_ID, VERSION_BODY_L_ID, DATA_INPUT_ID, FILTER_FIELDS, SID_RATE
from business.check_documents_in_edo.parsers import WebGuiParser, ExcelParser
from business.models.dto import Order
from config import ENV_DATA, TEMP_DIR


class WebGuiMain(WebGuiBase):

    def __init__(self):
        super().__init__(
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                                   'Chrome/85.0.4183.121 Safari/537.36', 'Accept': 'application/json'})

        self.parser = WebGuiParser()

    def load_transaction(self, transaction_name: str):
        """
        Метод предназначен чтобы открыть домашнюю страницу и перейти к транзакции
        :param transaction_name: Имя транзакции
        :return:
        """

        self.open_home_page()
        self.open_transaction(transaction_name)


class WebGuiExcelDownloader:

    def __init__(self, wb: WebGuiMain):
        """
        ВАЖНО! Класс юзабелен ПОСЛЕ ИНИЦИАЛИЗАЦИИ ОКНА СКАЧИВАНИЯ ОТЧЕТА
        """

        self.__wb = wb
        self.__file_bytes = None

    def download(self, download_path: WindowsPath) -> WindowsPath:
        """
        Скачивает отчет в указанную папку
        :param download_path: папка для скачивания
        :return: Путь до сохраненного файла
        """

        self.__click_next()
        self.__start_download_process()
        return self.__save_report(download_path)

    def __click_next(self):
        """
        Эмулирует нажатие кнопки "Дальше" в диалоговом окне выгрузки в ексель
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params=f'~RG_WEBGUI=X&sap-statistics=true&~SEC_SESSTOKEN={self.__wb.ses_token}',
            json=[{"post": "focus/wnd[1]/usr/radRB_OTHERS", "logic": "ignore"}, {"post": "vkey/0/ses[0]"},
                  {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[-1]['content']
        except:
            raise Exception(
                '%s. Не удалось отправить запрос на получение первого перфикса' % self.__click_next.__qualname__)

        path_prefix = self.__parse_prefix()

        http_data = HttpData(method=HttpMethod.POST,
            url=f'%s/%s/data/%s~query' % (self.__wb.path, path_prefix, self.__wb.ses_token), params='RetQuery=Z:', )
        self.__wb.send_request(http_data)

    def __start_download_process(self):
        """
        Запускает скачивание файла.
        :return:
        """

        self.__send_request_for_next_prefix()

        path_prefix = self.__parse_prefix()

        http_data = HttpData(method=HttpMethod.POST,
            url='%s/%s/data/%s~filesavedialog' % (self.__wb.path, path_prefix, self.__wb.ses_token),
            params='FileName=Z%3A%5Cexport.XLSX&FileEncoding=', )

        self.__wb.send_request(http_data)

        bytes_array = b''

        while True:

            self.__send_request_for_next_prefix()

            path_prefix = self.__parse_prefix()

            http_data = HttpData(method=HttpMethod.POST,
                url='%s/%s/data/%s~get' % (self.__wb.path, path_prefix, self.__wb.ses_token),
                params='FileName=Z%3A%5Cexport.XLSX&FileEncoding=', )

            file_part = self.__wb.send_request(http_data)

            if not file_part.content:
                break

            bytes_array += file_part.content

        self.__file_bytes = bytes_array

    def __send_request_for_next_prefix(self):
        """
        Метод отправляет запрос, в ответе которого приходит префикс для след запроса на скачивание файла
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params=f'~RG_WEBGUI=X&sap-statistics=true&~SEC_SESSTOKEN={self.__wb.ses_token}',
            json=[{"post": "okcode/ses[0]", "content": "OK"}, {"post": "vkey/0/ses[0]"}, {"get": "state/ur"}])
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[-1]['content']
        except:
            raise Exception(
                '%s. Не удалось отправить запрос на получение след префикса"' % self.__send_request_for_next_prefix.__qualname__)

    def __parse_prefix(self) -> str:
        """
        Метод ищет в тексте ответа префикс для запросов на скачивание файла
        :return:
        """

        part_path = parse_between("sap.its.communication.lockForApplet\('", "'\);]]", self.__page_text)

        if not part_path:
            raise ValueError('%s. Не удалось найти часть урла для скачивания ексель файла.')

        return part_path

    def __save_report(self, download_path: WindowsPath) -> WindowsPath:
        """
        Сохраняет отчет полученый из САМ
        :param download_path: папка для скачивания
        :return: Возвращает путь до сохраненного файла
        """

        try:

            if not self.__file_bytes:
                raise Exception('%s. Нет бинарника для скачивания' % self.__save_report.__qualname__)

            Path(download_path).write_bytes(self.__file_bytes)

            return download_path

        except Exception as err:
            raise Exception('%s. Не удалось сохранить файл \n  %s' % (self.__save_report.__qualname__, err))


class WebGuiME23NTransaction:

    def __init__(self, wb: WebGuiMain):
        self.__wb = wb
        self.__transaction_name = 'ME23N'
        self.__page_text = None
        self.__tables_id = {"Заголовок": "1", "Обзор позиций": "2", "Позиция подробно": "3"}
        self.__table_title_menu = {"Условия": {"request_id": "2", "active": False, "html_id": "M0:46:1:2:2:1:1::0:1"},
            "Версии": {"request_id": "18", "active": False, "html_id": "M0:46:1:2:2:1:1::0:17"}}

        wb.load_transaction(self.__transaction_name)

    def open_order(self, order_num: str):
        """
        Метод ищет и открывает заказ по номер 45-го.
        :param order_num: номер 45-го
        :return:
        """

        self.__click_open_other_order_button()
        self.__choose_document(order_num=order_num)
        self.__prepare_page()

    def get_netto(self) -> float:
        """
        Метод получает значение поля "Нетто" на вкладке "Условия"
        :return: Значение поля "Нетто"
        """

        if not self.__table_title_menu.get('Условия').get('active'):
            self.__open_title_menu('Условия')

        dirty_netto = self.__wb.parser.get_value_by_attr(self.__page_text, NETTO_INPUT_ID)

        try:
            # т.к. в один из тестов значение поля "Нетто" было <00.000,00 > была придумана эта костылина.
            netto_list = dirty_netto.replace(' ', '').replace(',', '.').split('.')
            return float("".join(netto_list[:-1]) + "." + netto_list[-1])

        except AttributeError:
            raise Exception('%s. Не удалось получить значение поля "Нетто"' % self.get_netto.__qualname__)

    def get_currency(self) -> str:
        """
        Метод получает значение поля "Валюта" на вкладке "Условия"
        :return: Значение поля "Валюта"
        """

        if not self.__table_title_menu.get('Условия').get('active'):
            self.__open_title_menu('Условия')

        currency = self.__wb.parser.get_value_by_attr(self.__page_text, CURRENCY_INPUT_ID)

        if not currency:
            raise Exception('%s. Не удалось получить значение поля "Нетто"' % self.get_netto.__qualname__)

        return currency

    def get_external_revision_number(self) -> tuple:
        """
        Метод получет значение из столбца "Внешний № изменения" у первой созданнйо строки (по дате создания)
        :return: Кортеж где первый элемент значение ячейки "Внешний номер изменения" где мин Дата создания, второй элем максимальная
        """

        if not self.__table_title_menu.get('Версии').get('active'):
            self.__open_title_menu('Версии')

        # SUUUPER костыль
        # Крч чтобы распарсить таблицу нужны id формата "24.148-mrss-hdr-left-content", где "24.148" меняется при каждом запуске.
        # Для этого ищем этот перфикс и добавляем его к id-шникам
        prefix_id = parse_between(start='id="grid#', stop='#', text=self.__page_text)

        result = self.__wb.parser.parse_webgui_table(cdata=self.__page_text,
                                                     header_left_id=VERSION_HEADER_L_ID % prefix_id,
                                                     header_right_id=VERSION_HEADER_R_ID % prefix_id,
                                                     body_right_id=VERSION_BODY_R_ID % prefix_id,
                                                     body_left_id=VERSION_BODY_L_ID % prefix_id)
        try:
            result.sort(key=lambda item: datetime.datetime.strptime(item.get('ДатаСоздан'), "%d.%m.%Y").date())

            return result[0].get('Внешний № изменения'), result[-1].get('Внешний № изменения')

        except:
            raise Exception(
                '%s. Не смог получить "Внешний № изменения"' % self.get_external_revision_number.__qualname__)

    def get_date(self) -> date:
        """
        Метод получает значение из поля "Дата"
        :return: значение из поля "Дата"
        """

        order_date = self.__wb.parser.get_value_by_attr(self.__page_text, DATA_INPUT_ID)

        if not order_date:
            raise Exception('%s. Не удалось получить значение поля "Дата"' % self.get_date.__qualname__)

        return datetime.datetime.strptime(order_date, "%d.%m.%Y").date()

    def __open_title_menu(self, menu_name: str):
        """
        Метод переходит по вкладкам в зависимости от их названия.
        :param menu_name: Название вкладки
        :return:
        """

        if not self.__table_title_menu.get(menu_name):
            raise ValueError('%s. Не корректное название меню' % self.__open_title_menu.__qualname__)

        menu_is_selected = self.__wb.parser.get_value_by_attr(self.__page_text,
                                                              self.__table_title_menu[menu_name]['html_id'], 'selected')

        if menu_is_selected == "true":
            self.__set_active_menu(menu_name)
            return

        saplmegui = self.__get_saplmegui()

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": f"action/4/wnd[0]/usr/subSUB0:SAPLMEGUI:{saplmegui}/subSUB1:SAPLMEVIEWS:1100"
                           f"/subSUB2:SAPLMEVIEWS:1200/subSUB1:SAPLMEGUI:1102/tabsHEADER_DETAIL/tabpTABHDT{self.__table_title_menu[menu_name]['request_id']}"},
                  {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[1]['content']
            self.__set_active_menu(menu_name)

        except Exception:
            raise Exception('%s. Не смог открыть меню %s.' % (self.__open_title_menu.__qualname__, menu_name))

    def __click_open_other_order_button(self):
        """
        Метод эмулирует нажатие кнопки "Другой заказ"
        :return:
        """
        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": "action/3/wnd[0]/tbar[1]/btn[17]"}, {"get": "state/ur"}], )
        self.__wb.send_request(http_data)

    def __choose_document(self, order_num: str):
        """
        Метод эмулирует выбор документа для поиска.
        :param order_num: номер 45-го
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"content": f"{order_num}", "post": "value/wnd[1]/usr/subSUB0:SAPLMEGUI:0003/ctxtMEPO_SELECT-EBELN"},
                  {"post": "action/304/wnd[1]/usr/subSUB0:SAPLMEGUI:0003/ctxtMEPO_SELECT-EBELN",
                   "content": "position=10", "logic": "ignore"}, {"post": "vkey/0/ses[0]"}, {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[3]['content']
        except Exception:
            raise Exception("%s. Не смог открыть выбранный документ" % self.__choose_document.__qualname__)

    def __prepare_page(self):
        """
        Метод подготавливает, найденную станицу, для парсинга.
        Открывает\Закрывает таблицы и открывает меню Условия.
        Для корректной работы должно быть:
            Заголовок -- Открыта
            Открыта вкладка "Условия"
        :return:
        """

        if "Поставка/счет" not in self.__page_text:
            self.__expand_table("Заголовок")

        self.__open_title_menu("Условия")

    def __expand_table(self, table_name: str):
        """
        Метод открывает\закрывает Таблицу "Заголовок"
        :param table_name: Название таблицы, которую нужно открыть или закрыть
        :return:
        """

        if table_name not in ("Заголовок", "Обзор позиций", "Позиция подробно"):
            raise ValueError(
                '%s. Не верное значение %s ожидалось одно из "Заголовок", "Обзор позиций", "Позиция подробно"' % (
                self.__expand_table.__qualname__, table_name))

        saplmegui = self.__get_saplmegui()

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{
                      "post": f"action/3/wnd[0]/usr/subSUB0:SAPLMEGUI:{saplmegui}/subSUB{self.__tables_id.get(table_name)}:SAPLMEVIEWS:1100/subSUB1:SAPLMEVIEWS:4000/btnDYN_4000-BUTTON"},
                  {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[1]['content']
        except Exception:
            raise Exception(
                '%s. Не смог Расскрыть/Свернуть таблицу %s.' % (self.__expand_table.__qualname__, table_name))

    def __get_saplmegui(self) -> str:
        """
        Метод ищет ID SAPLMEGUI для дальнейших запросов.
        Нужен ибо этот ID меняессть если открыть\закрыть какую-нибудь таблицу на странице.
        :return: id для запросов
        """

        found = re.findall('wnd\[0\]/usr/subSUB0:SAPLMEGUI:(.{4})', self.__page_text)

        try:
            return found[0]
        except IndexError:
            raise IndexError('%s. Не смог получить SAPLMEGUI' % self.__get_saplmegui.__qualname__)

    def __set_active_menu(self, menu_name: str):
        """
        Метод устанавливает флаг активной вкладки меню.
        :param menu_name: Название вкладки
        :return:
        """

        if not self.__table_title_menu.get(menu_name):
            raise ValueError('%s. Не корректное название меню' % self.__set_active_menu.__qualname__)

        for key, value in self.__table_title_menu.items():
            value['active'] = False if key != menu_name else True


class WebGuiOB08Transaction:

    def __init__(self, wb: WebGuiMain):
        self.__wb = wb
        self.__transaction_name = 'OB08'
        self.__page_text = None

        self.__load_transaction()

    def get_exchange_rate(self, curr: str, date_after: date):
        """
        Метод получает "Курс пересчета валют" по фильтрам
        :param curr: Валюта для поиска
        :param date_after: Дата начала действия курса
        :return:
        """
        self.__go_to_print()
        self.__open_filters()
        self.__choose_filters()
        self.__apply_choose_filters()
        result = self.__set_data_and_apply_filters(curr=curr, date_after=date_after)

        try:
            property_list = json.loads(result)['children'][0]['children'][0]['children'][5]['children']

            found_property = list(filter(lambda x: x['properties']['Sid'] == SID_RATE, property_list))

            dirty_rate = found_property[0]['properties']['Text']

            return float(dirty_rate.replace(',', '.').replace(' ', ''))

        except:
            raise Exception(
                '%s. Не удалось распарсить жуйсон для получения "Курса валюты"' % self.get_exchange_rate.__qualname__)

    def __go_to_print(self):
        """
        Метод эмулирует нажатие кнопки "Печать"
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": "action/3/wnd[0]/tbar[0]/btn[86]"}, {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[1]['content']
        except:
            raise Exception('%s. Не удалось нажать кнопку "Печать"' % self.__go_to_print.__qualname__)

    def __open_filters(self):
        """
        Метод эмулируетт нажатие кнопки "Фильтр"
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": "action/3/wnd[0]/tbar[1]/btn[29]"}, {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[1]['content']
        except:
            raise Exception('%s. Не удалось нажать кнопку "Фильтр"' % self.__open_filters.__qualname__)

    def __choose_filters(self):
        """
        Метод осуществляет выбор фильтров
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": "action/47/wnd[1]/usr/tblSAPLSKBHTC_FIELD_LIST_820", "content": "rows=;%s;%s;%s;" % (
            FILTER_FIELDS.get('Тип Курса'), FILTER_FIELDS.get('Исходная валюта'), FILTER_FIELDS.get('Действит. с'))},
                {"post": "action/304/wnd[1]/usr/tblSAPLSKBHTC_FIELD_LIST_820/txtGT_FIELD_LIST-SELTEXT[0,3]",
                 "content": "position=0", "logic": "ignore"}, {"post": "action/3/wnd[1]/usr/btnAPP_WL_SING"},
                {"get": "state/ur"}],

        )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[3]['content']
        except:
            raise Exception('%s. Не удалось выбрать фильтры' % self.__open_filters.__qualname__)

    def __apply_choose_filters(self):
        """
        Метод эмулирует нажатие кнопки "Скопировать" в окне фильтров.
        тем самым, применяя выбранные фильтры. хз почему она называется "Скопировать
        :return:
        """
        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": "action/304/wnd[1]/usr/tblSAPLSKBHTC_FIELD_LIST_820/txtGT_FIELD_LIST-SELTEXT[0,0]",
                   "content": "position=0", "logic": "ignore"}, {"post": "vkey/0/ses[0]"}, {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[2]['content']
        except:
            raise Exception('%s. Не удалось нажать кнопку "Скопировать"' % self.__open_filters.__qualname__)

    def __set_data_and_apply_filters(self, curr: str, date_after: date, curr_type: str = 'M') -> str:
        """
         Метод устанавливает данные в фильтр и применяет их.
        :param curr: Валюта для поиска
        :param date_after: Дата начала действия курса
        :param curr_type: Тип Курса в данном скрипте всегда М
        :return: json с инфой оо странице
        """

        if isinstance(date_after, date):
            date_for_request = date_after.strftime('%d.%m.%Y')
        else:
            date_for_request = date_after

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"content": curr_type,
                   "post": "value/wnd[1]/usr/ssub%_SUBSCREEN_FREESEL:SAPLSSEL:1105/ctxt%%DYN001-LOW"},
                {"content": curr, "post": "value/wnd[1]/usr/ssub%_SUBSCREEN_FREESEL:SAPLSSEL:1105/ctxt%%DYN002-LOW"},
                {"content": date_for_request, "post": "value/wnd[1]/usr/ssub%_SUBSCREEN_FREESEL:SAPLSSEL:1105/ctxt%%DYN003-LOW"},
                {"post": "action/304/wnd[1]/usr/ssub%_SUBSCREEN_FREESEL:SAPLSSEL:1105/ctxt%%DYN003-LOW",
                 "content": "position=10", "logic": "ignore"}, {"post": "vkey/0/ses[0]"}, {"get": "state/json"}], )
        resp = self.__wb.send_request(http_data)

        try:
            return resp.json()[5]['content']
        except:
            raise Exception('%s. Не удалось выбрать фильтры' % self.__open_filters.__qualname__)

    def __load_transaction(self):
        """
        Метод предназначен чтобы открыть транзакцию
        и после этого прожать кнопку "Дальше" на уведомление по правам
        :return:
        """

        self.__wb.load_transaction(self.__transaction_name)
        self.__click_warning()

    def __click_warning(self):
        """
        Метод пропускает предупреждение о недостатке прав.
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": "action/304/wnd[1]/usr/txtMESSTXT1", "content": "position=0", "logic": "ignore"},
                  {"post": "vkey/0/ses[0]"}, {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[2]['content']
        except:
            pass


class WebGuiZME3NTransaction:

    def __init__(self, wb: WebGuiMain):
        self.__wb = wb
        self.__transaction_name = 'ZME3N'
        self.__page_text = None
        self.__download_part_path = None

        wb.load_transaction(self.__transaction_name)

    def open_buy_document(self, number: str):
        """
        Метод ищет и открывает документ закупки по номеру 45-го.
        :param number: Номер 45-го
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params={'~RG_WEBGUI': 'X', 'sap-statistics': 'true', '~SEC_SESSTOKEN': self.__wb.ses_token, },

            json=[{"post": "value/wnd[0]/usr/ctxtEN_EKORG-LOW", "content": "", "logic": "ignore"},
                  {"content": number, "post": "value/wnd[0]/usr/ctxtEN_EBELN-LOW"},
                  {"post": "action/304/wnd[0]/usr/ctxtEN_EBELN-LOW", "content": "position=10", "logic": "ignore"},
                  {"post": "action/3/wnd[0]/tbar[1]/btn[8]"}, {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[-1]['content']
        except:
            raise Exception('%s. Не удалось нажать найти документ закупки' % self.open_buy_document.__qualname__)

    # noinspection PyTypeChecker
    def get_order_list(self) -> List[Order]:
        """
        Метод получает спискок товаров по документу.
        :return: Список отоваров
        """

        file_path = self.__download_report()

        excel_parser = ExcelParser(file_path=file_path)

        result = excel_parser.get_data()

        excel_parser.close_excel()

        order_list = tuple(map(lambda data: Order(data), result))

        if order_list:
            file_path.unlink()

        return order_list

    def __download_report(self) -> WindowsPath:
        """
        Метод скачивает ексель файл из которого, в дальнейшем будет получен список товаров
        :return:
        """

        self.__click_to_excel_button()

        excel_downloader = WebGuiExcelDownloader(wb=self.__wb)

        file_name = f'{datetime.datetime.today().strftime("%m.%d.%Y %H-%M")} report.xlsx'
        download_path = TEMP_DIR / file_name

        path_to_file = excel_downloader.download(download_path=download_path)

        return path_to_file

    def __click_to_excel_button(self):
        """
        Эмулирует нажатие на кнопку "Электронная таблица..."
        :return:
        """

        http_data = HttpData(method=HttpMethod.POST, url=f'{self.__wb.path}/batch/json',
            params=f'~RG_WEBGUI=X&sap-statistics=true&~SEC_SESSTOKEN={self.__wb.ses_token}',
            json=[{"post": "action/3/wnd[0]/tbar[1]/btn[43]"}, {"get": "state/ur"}], )
        resp = self.__wb.send_request(http_data)

        try:
            self.__page_text = resp.json()[-1]['content']
        except:
            raise Exception(
                '%s. Не удалось нажать на кнопку "Электронная таблица..."' % self.__click_to_excel_button.__qualname__)
