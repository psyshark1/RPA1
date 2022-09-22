import datetime
from pathlib import WindowsPath
from typing import List, Union

import pyodbc
from logger import log

from business.check_documents_in_edo.fiori_process import FioriMain, FioriIncomingDocuments, \
    FioriSearchForProcessesToChangeContracts
from business.check_documents_in_edo.parsers import PDFParser
from business.check_documents_in_edo.webgui_process import WebGuiMain, WebGuiZME3NTransaction, WebGuiME23NTransaction, \
    WebGuiOB08Transaction
from business.check_documents_in_edo.xml_process import XML
from business.models.dto import ReflectTask, TaskDocument, IncomingDocument, XMLData, Order
from business.utils import to_float, remove_temp
from config import ENV_DATA, LOGS_DIR
from db.logger import logger


# TODO Сделать парсинг екселя ввиде текста. Требуется для сравнения данных с УПД. Не реализовано т.к. нет примера екселя.

class CheckDocumentsInEdo:

    def __init__(self, task: ReflectTask):
        self.__fiori = None
        self.__fiori_incoming_doc = None
        self.__webgui = None
        self.__task = task
        self.__task_document = TaskDocument()

    @log.write_by_method
    def do_check(self) -> ReflectTask:
        """
        Запускает проверку документов в ЭДО
        :return: словарь с результатами
        """
        try:
            logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo', 'start_check',
                           'Info', 'Проверка документов в ЭДО', 'Начало проверки документов в ЭДО')

            self.__prepare_module_to_start()

            log.info(f'Начал проверять документы в ЭДО...')

            self.__task_document.date_rule = self.__get_date_rule(self.__task.contract_number)

            self.__login_in_systems()

            log.info(f'\tАвторизовался в системах SAP')

            self.__fiori_incoming_doc = FioriIncomingDocuments(self.__fiori)

            log.info(f'\tОткрыл в Fiori вкладку "Inbox входящие електронные документы"')

            incoming_documents = self.__fiori_incoming_doc.get_incoming_documents(self.__task)

            self.__task.edo_documents_count = len(incoming_documents)

            log.info(
                f'\tПолучил Входящие документы электронные документы. Количество: %s' % self.__task.edo_documents_count)

            try:
                # Если метод __separate_upd_document вернул ошибку, значит не нашлось UPD документа.
                upd_documents, other_docs = self.__separate_upd_document(inc_documents=incoming_documents)
            except Exception as be:
                logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo',
                               'Get UPD document', 'Warning', 'Проверка документов в ЭДО', be)
                return self.__prepare_task_to_return(status='2', message=be)

            upd_data = None
            upd_doc = None
            error_msg = []
            upd_validation_result = []
            for doc in upd_documents:
                doc_data = self.__parse_upd_document(upd_document=doc)
                upd_contractor_data_are_valid, err_msg = self.__compare_contractor_info(upd_data=doc_data)
                error_msg.append('%s: %s' % (doc.edo_number, err_msg))
                upd_validation_result.append(upd_contractor_data_are_valid)
                if not upd_data:# and upd_contractor_data_are_valid:
                    upd_doc = doc
                    upd_data = doc_data

            '''if all(not result for result in upd_validation_result):
                logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo',
                               'Check contractor', 'Warning', 'Проверка документов в ЭДО',
                               'Не пройдена проверка реквизитов в ЭДО')
                return self.__prepare_task_to_return(status='2',
                                                     message='Не пройдена проверка реквизитов в ЭДО. %s' % ';\n'.join(error_msg))'''

            self.__task_document.summ_without_nds = to_float(upd_data.summ_without_nds)
            self.__task_document.summa_with_nds = to_float(upd_data.summ_with_nds)
            self.__task_document.summa_nds = to_float(upd_data.nds_sum)
            self.__task_document.upd_date = upd_data.upd_date

            log.info(f'\tНачал проверять сведения о покупателе')

            log.info(f'\tСведения о покупателе корректны')

            # log.info(f'\tНачал сверку остальных документов в UPD...')
            #
            # other_docs_are_valid = self.__check_other_docs(other_docs, upd_data)
            #
            # if not other_docs_are_valid:
            #     logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo',
            #                    'Check Other docs', 'Warning', 'Проверка документов в ЭДО',
            #                    'Не пройдена проверка реквизитов в ЭДО')
            #     return self.__prepare_task_to_return(status='2', message='Не пройдена проверка реквизитов в ЭДО')
            #
            # log.info(f'\tОстальные документы корректны')

            me23n_transaction = WebGuiME23NTransaction(wb=self.__webgui)

            log.info(f'\tОткрыл транзакцию "ME23N"')

            me23n_transaction.open_order(order_num=self.__task.number_45)

            min_ccpm_number, max_ccpm_number = me23n_transaction.get_external_revision_number()

            log.info(f'\tПолучил номера CCPM')

            log.info(f'\tПолучаю атрибуты для основной модели.')

            self.__task_document.document_sum = round(me23n_transaction.get_netto(),2)
            self.__task_document.currency = me23n_transaction.get_currency()
            self.__task_document.order_date = me23n_transaction.get_date()
            self.__task_document.exchange_rate = self.__get_exchange_rate()

            log.info(f'\tПрисвоил "document_sum", "currency", "order_date", "exchange_rate" к основному объекту')

            fiori_search_process_to_change = FioriSearchForProcessesToChangeContracts(fiori=self.__fiori)

            log.info(f'\tОткрыл в Fiori вкладку "Поиск процессов по изменению договоров"')

            if self.__task_document.date_rule == 2:
                self.__task_document.recalc_date_fiori = fiori_search_process_to_change.get_document_date(
                    min_ccpm_number)

            zme3n_transaction = WebGuiZME3NTransaction(wb=self.__webgui)

            log.info(f'\tОткрыл транзакцию "ZME3N"')

            zme3n_transaction.open_buy_document(number=self.__task.number_45)
            orders = zme3n_transaction.get_order_list()

            log.info(f'\tПолучил список товаров')

            log.info(f'\tНачал проверку сумм товаров транзакции ZME3N и UPD документа...')

            edo_documents_by_sum_are_valid = self.__check_edo_document_sum(orders=orders)
            self.__task_document.document_sum = round(self.__task_document.document_sum,2)
            if not edo_documents_by_sum_are_valid:
                logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo',
                               'Check Other docs by positions', 'Warning', 'Проверка документов в ЭДО',
                               'Не пройдена проверка документов ЭДО по позициям')
                return self.__prepare_task_to_return(status='2',
                                                     message='ПО заданию ИД %s №%s не пройдена проверка документов ЭДО '
                                                             'по суммам в пакете %s'
                                                             % (self.__task.id, self.__task.number_45, upd_doc))

            log.info(f'\tСуммы товаров корректны')

            # log.info(f'\tНачал проверку по позициям товаров транзакции ZME3N и UPD документа...')
            #
            # edo_doc_by_positions_are_valid = self.__check_edo_documents_positions(orders=orders, upd_data=upd_data)
            #
            # if not edo_doc_by_positions_are_valid:
            #     logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo',
            #                    'Check Other docs by positions', 'Не пройдена проверка документов ЭДО по позициям')
            #     return self.__prepare_task_to_return(status='2',
            #                                          message='Не пройдена проверка документов ЭДО по позициям')
            #
            # log.info(f'\tПозиции товаров корректны')

            order_pdf_path = fiori_search_process_to_change.get_document_as_pdf(max_ccpm_number)

            primary_document_text = self.__parse_pdf(path=order_pdf_path)

            log.info(f'\tПолучил PDF заказа и распарсил его')

            log.info(f'\tНачал проверку данных заказа с данными UPD документа...')

            primary_document_are_valid, error_message = self.__check_primary_documents_with_upd_data(upd_data=upd_data,
                                                                                                     primary_document_text=primary_document_text)

            if not primary_document_are_valid:
                logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo',
                               'Check Oreder', 'Warning', 'Проверка документов в ЭДО',
                               'Не пройдена сверка первичных документов с заказом. Не пройдена проверка: %s'
                               % error_message)
                return self.__prepare_task_to_return(status='2',
                                                     message='Не пройдена сверка первичных документов с заказом. '
                                                             'Не пройдена проверка: %s в пакете %s'
                                                             % (error_message, upd_doc.edo_number))

            log.info(f'\tДанные заказа корректны')

            log.info(f'Закончил проверку документов в ЭДО')

            logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo', 'End of check',
                           'Info', 'Проверка документов в ЭДО', 'Закончил проверку документов в ЭДО')

            remove_temp()

            return self.__prepare_task_to_return()

        except Exception as ex:
            logger.set_log(f'{self.__task.number_45}', 'Reflect kz Automation', 'check_document_in_edo',
                           'Unknown error', 'Warning', 'Проверка документов в ЭДО',
                           'Неизвестная ошибка. %s' % str(ex).replace("'", ""))
            log.exception('Неизвестная ошибка. %s' % ex)
            return self.__prepare_task_to_return(status='2', message=ex)

    def __login_in_systems(self):
        """
        Метод авторизуется в системах необходимых для проверки документов
        :return:
        """

        if not self.__fiori:
            self.__fiori = FioriMain()
            self.__fiori.login(login=ENV_DATA['sap_fiori_login'], password=ENV_DATA['sap_fiori_pass'])

        if not self.__webgui:
            self.__webgui = WebGuiMain()
            self.__webgui.login(login=ENV_DATA['sap_gui_login'], password=ENV_DATA['sap_gui_pass'])

    def __separate_upd_document(self, inc_documents: List[IncomingDocument]) -> (
        List[IncomingDocument], List[IncomingDocument]):
        """
        Метод выделяет УПД документы из всего пула
        :param inc_documents: Пул документов
        :return: УПД документ
        """

        upd_types = ('UPD_S', 'UPD_D', 'UPD_S+D', 'OTORG')

        upd_docs = list(filter(lambda doc: doc.oed_doc_type in upd_types, inc_documents))
        other_docs = list(filter(lambda doc: doc.oed_doc_type not in upd_types, inc_documents))

        if not upd_docs:
            raise Exception('Не удалось найти ни одно документа с типом: "UPD_S", "UPD_D", "UPD_S+D", "OTORG"')

        return upd_docs, other_docs

    def __parse_upd_document(self, upd_document: IncomingDocument) -> XMLData:
        """
        Метод скачивает и парсит upd файл
        :param upd_document:  УПД документ для парсинга
        :return: XMLData
        """

        upd_path = self.__fiori_incoming_doc.download_document(document=upd_document)

        xml_parser = XML(upd_path, upd_document.oed_doc_type)

        try:
            xml_data = xml_parser.get_xml_data()
        except Exception:
            raise Exception('%s. Не удалось поулчить данные из ХМЛ файла' % self.__parse_upd_document.__qualname__)

        return xml_data

    def __compare_contractor_info(self, upd_data: XMLData) -> tuple:
        """
        Метод выполняет сравнение данных подрядчика из задания с даннми из UPD документа. И выполняет проверку стоимоссти товаров.
        :param upd_data: данные поулченные из xml файла
        :return: True or False, error message
        """

        full_product_price = 0

        for prod in upd_data.product:
            try:
                # Конвертим строку в инт. Строка в формате "4.0"
                prod_count_like_int = int(to_float(prod.get('prod_count')))
                price_like_float = to_float(prod.get('prod_price'))

                full_product_price += price_like_float * prod_count_like_int
            except:
                raise Exception(
                    '%s. Не удалось привести кол-во или цену к числовому формату' % self.__compare_contractor_info.__qualname__)

        contractor = self.__task.contractor

        if int(full_product_price) != int(to_float(upd_data.summ_without_nds)):
            return False, 'Не пройдена проверка стоимости без НДС. %s != %s' % (
                int(full_product_price), int(to_float(upd_data.summ_without_nds)))

        if 1 < full_product_price * 1.2 - to_float(upd_data.summ_with_nds) < -1:
            return False, 'Не пройдена проверка стоимости с НДС. %s != %s' % (
                int(full_product_price) * 1.2, int(to_float(upd_data.summ_with_nds)))

        if upd_data.inn_consignee != contractor.inn:
            return False, 'Не пройдена проверка ИНН грузополучаетля. %s != %s' % (upd_data.inn_consignee, contractor.inn)

        if upd_data.kpp_consignee != contractor.kpp:
            return False, 'Не пройдена проверка КПП грузополучаетля. %s != %s' % (upd_data.kpp_consignee, contractor.kpp)

        if upd_data.contractor_name_consignee != contractor.name:
            if upd_data.contractor_name_consignee not in contractor.name:
                if contractor.name not in upd_data.contractor_name_consignee:
                    # Головной офис мегафона слилися со столичным филиалом.
                    # Нужно делать проверку имени еще и со столичным.
                    capital_branch_name_parts = ('столичный', 'филиал ', 'пао', 'мегафон')
                    not_found_parts = tuple(filter(lambda x: x not in upd_data.contractor_name_consignee, capital_branch_name_parts))
                    if not_found_parts:
                        return False, 'Не пройдена проверка имени Грузополучателя. %s != %s' % (
                            upd_data.contractor_name_consignee, contractor.name)

        if not upd_data.city_consignee or not upd_data.street_consignee or not upd_data.house_consignee:
            if not upd_data.full_address_consignee:
                return False, 'Не пройдена проверка адреса Грузополучателя. Адресс не найден в UPD'
            else:
                if contractor.city not in upd_data.full_address_consignee or contractor.street not in upd_data.full_address_consignee or contractor.house not in upd_data.full_address_consignee:
                    return False, 'Не пройдена проверка адреса Грузополучателя. ' \
                                  'Один из параметров САП не найден в UPD адресе. SAP -- %s, UPD -- %s' % \
                           (', '.join([contractor.city, contractor.street, contractor.house]),
                            upd_data.full_address_consignee)
        else:

            if upd_data.city_consignee != contractor.city or upd_data.street_consignee != contractor.street or upd_data.house_consignee != contractor.house:
                return False, 'Не пройдена проверка адреса Грузополучателя. ' \
                              'Один из параметров САП не найден в UPD адресе. SAP -- %s, UPD -- %s' % \
                       (', '.join([contractor.city, contractor.street, contractor.house]),
                        ', '.join([upd_data.city_consignee, upd_data.street_consignee, upd_data.house_consignee]))

        if contractor.inn != upd_data.inn_buyer:
            return False, 'Не пройдена проверка ИНН Покупателя. %s != %s' % (upd_data.inn_buyer, contractor.inn)

        if contractor.kpp != upd_data.kpp_buyer:
            return False, 'Не пройдена проверка КПП Покупателя. %s != %s' % (upd_data.kpp_buyer, contractor.kpp)

        if 'мегафон' not in upd_data.contractor_name_buyer:
            return False, 'Не пройдена проверка Имени Покупателя. %s != ПАО "Мегафон"' % upd_data.contractor_name_buyer

        if upd_data.city_buyer and 'москва' not in upd_data.city_buyer:
            return False, 'Не пройдена проверка Города Покупателя. %s != Москва' % upd_data.city_buyer

        if upd_data.street_buyer and 'оружейный' not in upd_data.street_buyer:
            return False, 'Не пройдена проверка Улицы Покупателя. %s != Оружейный' % upd_data.street_buyer

        if upd_data.house_buyer and '41' not in upd_data.house_buyer:
            return False, 'Не пройдена проверка имени Покупателя. %s != 41' % upd_data.house_buyer

        if upd_data.full_address_buyer:
            required_address_parts = ['москва', 'оружейный', '41']
            not_found_parts = tuple(filter(lambda x: x not in upd_data.full_address_buyer, required_address_parts))
            if not_found_parts:
                return False, 'Не пройдена проверка адреса Покупателя. ' \
                              'Параметр(ы) %s не найден(ы) в UPD адресе -- %s' % (', '.join(not_found_parts), upd_data.full_address_buyer)

        return True,

    def __get_date_rule(self, contract_num: str) -> int:
        """
        Метод забирает из базы правило даты по номеру контракта
        :param contract_num: номер контракта
        :return: Парвило даты
        """

        dns = ENV_DATA['db_dsn']
        table = 'RPA1079_Sum_Check_Rule'

        with pyodbc.connect(dns) as connection:
            cursor = connection.cursor()
            cursor.execute("select Date_Rule from %s where Contract = '%s'" % (table, contract_num))

            if not cursor.rowcount:
                raise ValueError('%s. Не смог найти правило даты по номеру контракта %s.' % (
                    self.__get_date_rule.__qualname__, contract_num))

            row = cursor.fetchone()
            return row[0]

    def __check_other_docs(self, incoming_other_docs: List[IncomingDocument], upd_info: XMLData) -> tuple:
        """
        Метод скачивает остальные документы, парсит их и смраввнивает инфу в них с инфой их упд файла.
        :param incoming_other_docs: не формализованные документы
        :param upd_info: инфа полученная из xml upd документа.
        :return: True or False, error msg
        """

        for doc in incoming_other_docs:
            doc_path = self.__fiori_incoming_doc.download_document(document=doc)
            text = ''

            if doc_path.suffix == '.pdf':
                text = self.__parse_pdf(doc_path).lower()
            else:
                continue

            requisites_keys = ('inn', 'kpp', 'contractor_name')
            address_keys = ('city', 'street', 'house')

            for pos in requisites_keys:
                if upd_info.__dict__.get(pos) not in text:
                    return False, 'В PDF файле %s не найден %s со значением %s' % (doc.filename, pos, upd_info.__dict__.get(pos))

            if not upd_info.full_address_consignee:
                for pos in address_keys:
                    value = upd_info.__dict__.get(pos)

                    if value not in text:
                        return False, 'Не смог найти %s со значением %s в PDF файле %s' % (pos, value, doc.filename)
            else:
                address_parts = upd_info.full_address_consignee.split(', ')
                not_found_parts = tuple(filter(lambda x: x not in text, address_parts))
                if not_found_parts:
                    return False, 'Не смог найти части адреса %s в PDF файле %s' % (', '.join(not_found_parts), doc.filename)

        return True,

    def __parse_pdf(self, path: WindowsPath) -> str:
        """
        Метод получает данные из пдф файла
        :param path: путь до файла
        :return: текст из файла
        """
        pdf_parser = PDFParser(pdf_path=path)

        return pdf_parser.get_text()

    def __parse_excel(self, path: WindowsPath) -> any:
        """
        Метод получает данные из excel файла
        :param path: путь до файла
        :return: данные из файла
        """

        # Метод будет реализован, как только снова попадется файл в формате xml
        raise ValueError('Найден ексель файл. Данный метод не реализован. Передайте данные разработчку'
                         ' для тестирования и разработки')

    def __check_edo_document_sum(self, orders: List[Order]) -> bool:
        """
        Метод выполняет проверку документов ЭДО по суммам
        :param orders: Список Матеириалов полученный  из транзакции ZME3N
        :return: True or False
        """

        if self.__task.delivery_type == 2:

            orders_sum = 0

            for volume in self.__task.volume_list:

                try:
                    found_order = list(filter(lambda order: order.position == volume.pos_prd_doc, orders))[0]
                except IndexError:
                    raise AttributeError(
                        '%s. Не удалось найти ни одного материала по объему.' % self.__check_edo_document_sum.__qualname__)

                if volume.delivery_volume == found_order.product_count:
                    orders_sum += found_order.order_cost
                else:
                    orders_sum += found_order.cost_netto * found_order.product_count

            self.__task_document.document_sum = orders_sum

        if self.__task_document.exchange_rate:
            self.__task_document.document_sum = self.__task_document.document_sum * self.__task_document.exchange_rate

        if 1 < self.__task_document.summ_without_nds - self.__task_document.document_sum or self.__task_document.summ_without_nds - self.__task_document.document_sum < -1:
            return False
        if 1 < self.__task_document.summa_with_nds - self.__task_document.document_sum * 1.2 or self.__task_document.summa_with_nds - self.__task_document.document_sum * 1.2 < -1:
            return False
        if 1 < self.__task_document.summa_nds - self.__task_document.document_sum * 0.2 or self.__task_document.summa_nds - self.__task_document.document_sum * 0.2 < -1:
            return False
        if self.__task_document.summa_with_nds == self.__task_document.document_sum * 1.2:
            return False
        if self.__task_document.summa_nds == self.__task_document.document_sum * 0.2:
            return False

        return True

    def __get_exchange_rate(self) -> Union[None, float]:
        """
        Метод определяет дату пересчета и получает курс валюты по полученой дате
        :return: курс валюты
        """

        if self.__task_document.date_rule == 1:
            return None

        ob08_transaction = WebGuiOB08Transaction(wb=self.__webgui)

        date_after = None

        if self.__task_document.date_rule == 2:
            date_after = self.__task_document.order_date
        elif self.__task_document.date_rule == 3:
            date_after = self.__task.signing_date_mgf_side
        elif self.__task_document.date_rule == 4:
            date_after = self.__task.signing_date_ka_side
        elif self.__task_document.date_rule == 5:
            date_after = self.__task_document.upd_date
        else:
            raise AttributeError('%s. Не корректно значение для атрибута "Правило даты". Ожидал 1-5. Получил %s' %
                                 (self.__check_edo_documents_positions.__qualname__, self.__task_document.date_rule))

        return ob08_transaction.get_exchange_rate(curr=self.__task_document.currency, date_after=date_after)

    def __check_edo_documents_positions(self, orders: List[Order], upd_data: XMLData) -> bool:
        """
        Метод выполняет проверку документов ЭДО по позициям
        :param orders: Список Матеириалов полученный  из транзакции ZME3N
        :param upd_data: Данные полученные их XML
        :return: True or False
        """

        unique_orders = list()

        # Поиск уникальных позиций по коду материала
        for order in orders:

            found_unique_order = tuple(filter(lambda x: order.material_code == x.material_code, unique_orders))

            if not found_unique_order:
                unique_orders.append(order)

        # В списке всех позиций ищем совпадения с уникальным и складываем их количество
        for unique_order in unique_orders:
            found_same_orders = tuple(filter(lambda x: unique_order.material_code == x.material_code, orders))

            if not found_same_orders:
                raise Exception(
                    '%s.Что-то пошлно не так в мега логике' % self.__check_edo_documents_positions.__qualname__)

            if len(found_same_orders) == 1:
                continue

            unique_order.product_count = 0
            for same_order in found_same_orders:
                unique_order.product_count += same_order.product_count

        # Выполняется основная проверка. По спецификациям полученным из ХМЛ документа ищем позицию и сверяем ихз кол-во
        for prod in upd_data.product:

            ex_rate = self.__task_document.exchange_rate if self.__task_document.exchange_rate else 1

            found_order_by_specification = tuple(filter(
                lambda x: int(to_float(prod.get('prod_count'))) == x.product_count and (
                    1 > to_float(prod.get('prod_price')) - (x.cost_netto * ex_rate) > -1), unique_orders))

            if len(found_order_by_specification) > 1:
                raise Exception(
                    '%s.Что-то пошло не так. Найден больше чем один ордер.' % self.__check_edo_documents_positions.__qualname__)

            if not found_order_by_specification:
                return False

        return True

    def __check_primary_documents_with_upd_data(self, upd_data: XMLData, primary_document_text: str) -> tuple:
        """
        Метод осуществляет проврку первичных документов с заказом
        :param upd_data: Данные из ХМЛ УПД-хи
        :param primary_document_text: Текст пдф документа заказа
        :return:  кортеж (True or False, <Сообщение об ошибке>)
        """

        full_price_float = 0

        for prod in upd_data.product:

            if not self.__check_str_in_text(prod.get('article'), primary_document_text) or not self.__check_str_in_text(prod.get('code'), primary_document_text):
                if not self.__check_str_in_text(prod.get('prod_name'), primary_document_text):
                    return False, 'Артикул\код -- %s и Наименование товара -- %s не найдены в заказе' \
                           % (prod.get('article') or prod.get('article'), prod.get('prod_name'))

            try:
                # Конвертим строку в инт. Строка в формате "4.0"
                prod_count_like_int = int(to_float(prod.get('prod_count')))
                price_like_float = to_float(prod.get('prod_price'))

                product_price = price_like_float * prod_count_like_int
            except:
                raise Exception('%s. Не удалось привести кол-во или цену к числовому формату' %
                                self.__check_primary_documents_with_upd_data.__qualname__)

            if self.__task.delivery_type == 2:
                return True, ''

            if self.__task_document.date_rule != 1:
                product_price = product_price / self.__task_document.exchange_rate

            full_price_float += product_price

            str_price = self.__transformation_float_to_str_as_in_the_order(product_price)

            if str_price in primary_document_text:
                continue
            else:
                return False, 'В документе заказа не найдена цена: %s. Для продукта: %s' % (
                    product_price, prod.get("code"))

        full_price_str = self.__transformation_float_to_str_as_in_the_order(full_price_float * 1.2)

        if full_price_str not in primary_document_text:
            return False, 'В документе заказа не найдена общая цена с НДС: %s' % full_price_str

        return True, ''

    def __transformation_float_to_str_as_in_the_order(self, price: float) -> str:
        """
        Метод преобразует float к формату, который требуется для проверка наличия в заказе.
        :param price: цена в формате float
        :return: цена в формате str
        """

        try:
            # Округляем дробную часть до 2ух цифр и преобразуем число к строке
            two_digits_price_like_str = str(round(price, 2))
            # Делим строку по точке, отделяя целую и дробную части
            price_split_list = two_digits_price_like_str.split('.')
            # Переворачиваем целую часть
            reversed_integer_part = price_split_list[0][::-1]
            # Делим перевернутую целую часть по 3 символа.
            divided_int_part = [reversed_integer_part[i:i + 3] for i in range(0, len(reversed_integer_part), 3)]
            # Объединяем полученный массив в строку и обратно ее переворачиваем
            integer_price_part = ' '.join(divided_int_part)[::-1]
            # Объединяем полученную целую часть с дробной
            return '%s,%s' % (integer_price_part, price_split_list[-1])
        except:
            raise Exception('%s. Не удалось приобразовать число %s к формату для сверки с заказом.' % (
                self.__transformation_float_to_str_as_in_the_order.__qualname__, price))

    def __check_str_in_text(self, value: str, text: str) -> bool:
        """
        Проверяет наличие значения в тексте.
        :param value: значение
        :param text: текст
        :return: True or False
        """

        if not value:
            return False

        if value in text:
            return True
        else:
            return False

    def __prepare_task_to_return(self, status: str = None, message: any = None) -> ReflectTask:
        """
        Метод Заполняет основной объект данными
        :param status: 2 or None
        :param message: сообщение об ошибке
        :return: dict
        """

        self.__task.document = self.__task_document

        if status:
            self.__task.status = status

        if message:
            if self.__task.comment is not None:
                self.__task.comment = self.__task.comment + str(message) + ';'
            else:
                self.__task.comment = str(message) + ';'

        return self.__task

    def __prepare_module_to_start(self):
        """
        Метод предназначен для того, чтобы подготовить модуль к старту.
        :return:
        """

        log.add(dir_path=LOGS_DIR / 'check_documents_in_edo_logs')

    # Метод может понаддобиться если бизнес не устроит курс доллара из САП
    # def __get_rate_from_cbr_ru(self, curr_date: datetime, currency: str) -> float:
    #     """
    #     Получает ккурс валюты с сайта http://www.cbr.ru
    #     :param curr_date: дата поиска
    #     :param currency: валюта поиска
    #     :return: курс валюты
    #     """
    #  #     valute_rate = 0  #
    #     date_in_format = curr_date.strftime('%d/%m/%Y')  #
    #     resp = requests.get('http://www.cbr.ru/scripts/XML_daily.asp?date_req=%s' % date_in_format)  #
    #     xml_string = resp.text  #  #     tree = ET.ElementTree(ET.fromstring(xml_string))  #
    #     valute_list = [elem for elem in tree.findall('.//Valute')]  #
    #     for valute in valute_list:  #
    #         valute_currency = valute.findall('.//CharCode')[0].text  #
    #         if valute_currency == currency:  #
    #             valute_rate = valute.findall('.//Value')[0].text  #             break  #
    #     try:  #         float_rate = float(valute_rate.replace(' ', '').replace(',', '.'))
    #     except ValueError:
    #         raise Exception('%s. Не удалось преобразовать курс из строки в флоат' % self.__get_rate_from_cbr_ru.__qualname__)  #  #     return float_rate
