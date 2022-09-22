import datetime
from typing import Union, List


class TaskDocument:
    """Модель Документа"""
    def __init__(self, upd_date: str = None, date_rule: str = None, summ_without_nds: float = None, summa_with_nds: float = None, summa_nds: float = None,
                 order_date: str = None, currency: str = None, recalc_date_fiori: str = None, document_sum: str = None, exchange_rate: float = None):

        self.upd_date = upd_date,  # Дата УПД
        self.date_rule = date_rule,  # Правило даты
        self.summ_without_nds = summ_without_nds,  # Сумма без НДС
        self.summa_with_nds = summa_with_nds,  # Сумма с НДС
        self.summa_nds = summa_nds,  # Сумма НДС
        self.document_sum = document_sum,  # Сумма документа
        self.order_date = order_date,  # Дата заказа
        self.currency = currency,  # Валюта
        self.recalc_date_fiori = recalc_date_fiori,  # Дата пересчета FIORI
        self.exchange_rate = exchange_rate,  # Курс валюты


class TaskContractor:
    """Модел контрагента"""
    def __init__(self, name: str = None, inn: str = None, kpp: str = None, street: str = None,
                 house: str = None, city: str = None, subscriber: str = None):

        self.name = name  # Имя контрагента
        self.inn = inn  # ИНН
        self.kpp = kpp  # КПП
        self.street = street  # Улица
        self.house = house  # Дом
        self.city = city  # Город
        self.subscriber = subscriber  # Подписант


class TaskDeliveryVolume:
    """Модель объем поставки"""
    def __init__(self,
                 buy_document: str = None,
                 pos_prd_doc: str = None,
                 delivery_volume: str = None,

                 ):
        self.buy_document = buy_document  # Документ закупки
        self.pos_prd_doc = pos_prd_doc  # Позиция
        self.delivery_volume = delivery_volume  # Объем поставки


class ReflectTask:
    """Общаяя модель задания"""

    def __init__(self, id: int, number_45: str, number_18: str, date_18: str, edo_numbers: str, user_fio: str,
                 delivery_date: str,  delivery_type: int, edo_documents_count: int = 0, complete_datetime: str = None,
                 status: str = None, result: str = None, author: str = None, factory: str = None, number_50: str = None,
                 line_count: int = None, name_ka: str = None, contract_number: str = None,
                 signing_date_ka_side: str = None, signing_date_mgf_side: str = None, number_214: str = None,
                 processing_date: str = None, comment: str = None):

        self.id = id  # ID Задания в БД
        self.number_45 = number_45  # Номер 45
        self.number_18 = number_18  # Номер 18
        self.date_18 = date_18  # Дата 18*
        self.__edo_numbers = edo_numbers  # Перечень номеров ЭДО
        self.user_fio = user_fio  # ФИО пользователя
        self.author = author  # Автор
        self.delivery_date = delivery_date  # Дата поставки
        self.delivery_type = delivery_type  # Вид поставки
        self.status = status  # Статус задания
        self.result = result  # Результат выполнения задания
        self.complete_datetime = complete_datetime  # Дата-время отработки записи
        self.edo_documents_count = edo_documents_count  # Количество документов ЭДО
        self.comment = comment  # Комментарий

        # Результат работы Этап 2 или 4
        self.factory = factory  # Завод

        # Результат работы Этап 2
        self.number_50 = number_50  # Номер 50
        self.__volume_list = None  # Список объемов

        # Результат работы Этап 3
        self.line_count = line_count  # Количество строк
        self.name_ka = name_ka  # Наименование КА
        self.contract_number = contract_number  # Номер договора

        # Результат работы Этап 3 или  6
        self.signing_date_ka_side = signing_date_ka_side  # Дата подписания заказа со стороны КА
        self.signing_date_mgf_side = signing_date_mgf_side  # Дата подписания заказа со стороны МФ

        # Результат работы Этап 8
        self.number_214 = number_214  # Номер 214
        self.processing_date = processing_date  # Дата проводки

        # Результат работы Этап 5
        self.__contractor = None  # Инфа по контрагенту

        # Результат работы Этап 6
        self.__document = None  # Список документов

    @property
    def document(self) -> Union[None, TaskDocument]:
        """
        Возвращает TaskDocument
        :return: Union[None, List[TaskDocument]]
        """
        return self.__document

    @document.setter
    def document(self, doc: TaskDocument):
        """
        "сетит" TaskDocument
        :param doc: документ сформированный на этапе 6
        :return:
        """

        if not isinstance(doc, TaskDocument):
            raise ValueError('Ожидалось TaskDocument получил %s' % type(doc))

        self.__document = doc

    @property
    def contractor(self) -> Union[None, TaskContractor]:
        """
        Возвращает контрагента
        :return: Union[None, TaskContractor]
        """
        return self.__contractor

    @contractor.setter
    def contractor(self, item: TaskContractor):
        """
        "сетит" контрагента
        :param item: контрагент
        :return:
        """

        if not isinstance(item, TaskContractor):
            raise ValueError('Ожадилось TaskDocument получил %s' % type(item))

        self.__contractor = item

    @property
    def volume_list(self) -> Union[None, List[TaskDeliveryVolume]]:
        """
        Возвращает Список объемов
        :return: Union[None, List[TaskDeliveryVolume]]
        """
        return self.__volume_list

    @volume_list.setter
    def volume_list(self, items: List[TaskDeliveryVolume]):
        """
        "сетит" Список объемов
        :param items: список "Объем поставки"
        :return:
        """

        if tuple(filter(lambda item: not isinstance(item, TaskDeliveryVolume), items)):
            raise ValueError('Ожидалось List[TaskDeliveryVolume] получил %s' % tuple(map(lambda item: not type(item), items)))

        self.__volume_list = items

    @property
    def edo_numbers(self) -> List[str]:
        """
        Возвращает либо номер ЭДО либо список документов ЭДО
        Т.к в поле edo_numbers можжет быть либо 1 номер либо несколько с разделителем ";"
        :return:
        """
        try:
            split_value = self.__edo_numbers.replace(' ', '').replace(',', ';').split(';')

            return list(map(lambda x: x.strip(), split_value))
        except Exception as ex:
            raise Exception('Что то пошлно не так см. ReflectTask.edo_numbers \n Перечень номеров ЭДО %s' % self.__edo_numbers)


class IncomingDocument:

    def __init__(self, data):
        self.__data = data
        self.oed_doc_type = self.__data.get('DocumentOEDDocTyp')
        self.doc_uuid = self.__data.get('DocumentUUID')
        self.initiator = self.__data.get('DocumentInitiator')
        self.company_code = self.__data.get('CompanyCode')
        self.doc_id = self.__data.get('DocumentID')
        self.proc_id = self.__data.get('processid')
        self.filename = self.__data.get('FileName')
        self.edo_number = self.__data.get('DocumentShpNr')

    def __str__(self):
        return self.filename

    def __repr__(self):
        return self.__class__.__name__


class Order:

    def __init__(self, data):
        self.__data = data
        self.position = data.get('Позиция')
        self.material_name = data.get('Краткий текст')
        self.product_count = data.get('Количество заказа')
        self.material_code = data.get('Материал')
        self.cost_netto = data.get('Цена нетто')
        self.order_cost = data.get('СтоимЗаказа нетто')
        self.currency = data.get('Валюта')
        self.contractor_code = data.get('Код поставщика')
        self.delivery_volume = data.get('Объем поставки')
        self.manufacturer_part_number = data.get('№ ДеталПроизводителя')

    def __str__(self):
        return self.material_name

    def __repr__(self):
        return self.__class__.__name__


class XMLData:

    def __init__(self, inn_consignee: str = None,
                 kpp_consignee: str = None,
                 contractor_name_consignee: str = None,
                 city_consignee: str = None,
                 street_consignee: str = None,
                 house_consignee: str = None,
                 full_address_consignee: str = None,
                 inn_buyer: str = None,
                 kpp_buyer: str = None,
                 contractor_name_buyer: str = None,
                 city_buyer: str = None,
                 street_buyer: str = None,
                 house_buyer: str = None,
                 full_address_buyer: str = None,
                 upd_date: str = None,
                 summ_without_nds: str = None,
                 summ_with_nds: str = None,
                 nds_sum: str = None,
                 product: dict = None):
        self.inn_consignee = inn_consignee
        self.kpp_consignee = kpp_consignee
        self.contractor_name_consignee = contractor_name_consignee
        self.city_consignee = city_consignee
        self.street_consignee = street_consignee
        self.house_consignee = house_consignee
        self.full_address_consignee = full_address_consignee
        self.inn_buyer = inn_buyer
        self.kpp_buyer = kpp_buyer
        self.contractor_name_buyer = contractor_name_buyer
        self.city_buyer = city_buyer
        self.street_buyer = street_buyer
        self.house_buyer = house_buyer
        self.full_address_buyer = full_address_buyer
        self.upd_date = upd_date
        self.summ_without_nds = summ_without_nds
        self.summ_with_nds = summ_with_nds
        self.nds_sum = nds_sum
        self.product = product


class XMLRoute:

    def __init__(self, route: str, attr: str = None, value: bool = False):
        self.route = route
        self.attr = attr
        self.value = value
