import xml.etree.ElementTree as elTree
from abc import ABC, abstractmethod
from pathlib import WindowsPath
from typing import Union

from lxml import etree

from business.models.dto import XMLData, XMLRoute
from config import XSD_SCHEMAS_DIR


class PropertyInterface(ABC):

    @property
    @abstractmethod
    def inn_consignee(self):
        pass

    @property
    @abstractmethod
    def kpp_consignee(self):
        pass

    @property
    @abstractmethod
    def contractor_name_consignee(self):
        pass

    @property
    @abstractmethod
    def city_consignee(self):
        pass

    @property
    @abstractmethod
    def street_consignee(self):
        pass

    @property
    @abstractmethod
    def house_consignee(self):
        pass

    @property
    @abstractmethod
    def full_address_consignee(self):
        pass

    @property
    @abstractmethod
    def inn_buyer(self):
        pass

    @property
    @abstractmethod
    def kpp_buyer(self):
        pass

    @property
    @abstractmethod
    def contractor_name_buyer(self):
        pass

    @property
    @abstractmethod
    def city_buyer(self):
        pass

    @property
    @abstractmethod
    def street_buyer(self):
        pass

    @property
    @abstractmethod
    def house_buyer(self):
        pass

    @property
    @abstractmethod
    def full_address_buyer(self):
        pass

    @property
    @abstractmethod
    def upd_date(self):
        pass

    @property
    @abstractmethod
    def summ_without_nds(self):
        pass

    @property
    @abstractmethod
    def summ_with_nds(self):
        pass

    @property
    @abstractmethod
    def nds_sum(self):
        pass

    @property
    @abstractmethod
    def product(self):
        pass


class XML:

    def __init__(self, xml_path: WindowsPath, xml_type: str):
        self.__xml_path = xml_path
        self.__xml_type = xml_type
        self.__xml_bindings = {
            "UPD_S": globals().get('UPDRoutesContainer'),
            "UPD_D": globals().get('UPDRoutesContainer'),
            "UPD_S+D": globals().get('UPDRoutesContainer'),
            "OTORG": None,
        }

    def get_xml_data(self) -> Union[XMLData, None]:
        """
        Метод собирает необходимую по ТЗ инфу с хмл документа
        :return: XMLData
        """

        # Определяем какой у нас хмл по типу
        xml_type_class = self.__xml_bindings.get(self.__xml_type)
        xml_routes_container = xml_type_class()

        if not xml_routes_container:
            return None

        xml_data = XMLData()

        # Получаем все атрибуты класса XMLData и идем по ним циклом, чтобы заполнить их значениями
        for key, value in xml_data.__dict__.items():
            xml_route = None
            # Если в контейнере маршрутов есть ключ из класса XMLData, то забираем маршрут до значения
            if hasattr(xml_routes_container, key):
                xml_route = xml_routes_container.__getattribute__(key)

            # Если маршрут является просто экземплром класса XMLRoute, то получаем значение по этому роуту
            if isinstance(xml_route, XMLRoute):
                xml_data.__dict__[key] = self.__get_value_by_route(xml_route)

            # Если маршрут является словарем с маршрутами XMLRoute, то получаем словарь заполненый значениями по этим маршрутам
            if isinstance(xml_route, dict):
                xml_data.__dict__[key] = self.__get_dict_by_routes(xml_route)

        return xml_data

    # noinspection PyTypeChecker
    def __get_value_by_route(self, xml_route: XMLRoute) -> Union[None, list]:
        """
        Метод получает значение из ХМЛ по маршруту
        :param xml_route: XMLRoute
        :return: Union[None, list]
        """

        if not xml_route:
            return None

        root = elTree.parse(self.__xml_path)
        result = list()

        for elem in root.findall(xml_route.route):

            if xml_route.attr:
                try:
                    result.append(elem.attrib.get(xml_route.attr).lower())
                except AttributeError:
                    result.append(elem.attrib.get(xml_route.attr))

            if xml_route.value:
                result.append(elem.text)

        if not result:
            return None

        if len(result) == 1:
            return result[0]

        return result

    # noinspection PyTypeChecker
    def __get_dict_by_routes(self, xml_route_dict: dict) -> Union[None, list]:
        """
        Метод собирает список словарей из ХМЛ по словарю с маршрутами
        :param xml_route_dict: словарь с маршрутами XMLRoutes
        :return: Union[None, list]
        """

        # Проверка что словарь существует
        if not xml_route_dict:
            return None

        root = elTree.parse(self.__xml_path)
        result = None

        # Начинаем цикл по словарю
        for key, xml_route in xml_route_dict.items():

            # Проверка что маршрут существет
            if not xml_route:
                continue

            # Поиск елементов по маршруту
            found_elements = root.findall(xml_route.route)

            # Если массив с результатами еще не создан и не заполенен пустыми словарями - заполняем его
            # количество пустых словарей зависит от количества найденых елементов
            if not result:
                result = [dict() for f in range(len(found_elements))]

            # Начинаем цикл по найденым елементам
            for count, elem in enumerate(root.findall(xml_route.route)):

                # Конструкция result[count][key] обозначет, что мы добавляем значение по ключу в словарь в зависимости от итерации с найдеными елементами

                if xml_route.attr:
                    result[count][key] = elem.attrib.get(xml_route.attr)

                if xml_route.value:
                    result[count][key] = elem.text

        if not result:
            return None

        return result


class Torg12RoutesContainer:
    pass


class UPDRoutesContainer(PropertyInterface):
    inn_consignee = XMLRoute(route='.//ГрузПолуч/ИдСв/СвЮЛУч', attr='ИННЮЛ')
    kpp_consignee = XMLRoute(route='.//ГрузПолуч/ИдСв/СвЮЛУч', attr='КПП')
    contractor_name_consignee = XMLRoute(route='.//ГрузПолуч/ИдСв/СвЮЛУч', attr='НаимОрг')
    city_consignee = XMLRoute(route='.//ГрузПолуч/Адрес/АдрРФ', attr='Город')
    street_consignee = XMLRoute(route='.//ГрузПолуч/Адрес/АдрРФ', attr='Улица')
    house_consignee = XMLRoute(route='.//ГрузПолуч/Адрес/АдрРФ', attr='Дом')
    full_address_consignee = XMLRoute(route='.//ГрузПолуч/Адрес/АдрИнф', attr='АдрТекст')
    inn_buyer = XMLRoute(route='.//СвПокуп/ИдСв/СвЮЛУч', attr='КПП')
    kpp_buyer = XMLRoute(route='.//СвПокуп/ИдСв/ИдСв', attr='АдрТекст')
    contractor_name_buyer = XMLRoute(route='.//СвПокуп/ИдСв/ИдСв', attr='НаимОрг')
    city_buyer = XMLRoute(route='.//СвПокуп/Адрес/АдрРФ', attr='Город')
    street_buyer = XMLRoute(route='.//СвПокуп/Адрес/АдрРФ', attr='Улица')
    house_buyer = XMLRoute(route='.//СвПокуп/Адрес/АдрРФ', attr='Дом')
    full_address_buyer = XMLRoute(route='.//СвПокуп/Адрес/АдрИнф', attr='АдрТекст')
    upd_date = XMLRoute(route='.//Документ/СвСчФакт', attr='ДатаСчФ')
    summ_without_nds = XMLRoute(route='.//ТаблСчФакт/ВсегоОпл', attr='СтТовБезНДСВсего')
    summ_with_nds = XMLRoute(route='.//ТаблСчФакт/ВсегоОпл', attr='СтТовУчНалВсего')
    nds_sum = XMLRoute(route='.//ТаблСчФакт/ВсегоОпл/СумНалВсего/СумНал', value=True)
    product = dict(
        prod_name=XMLRoute(route='.//ТаблСчФакт/СведТов', attr='НаимТов'),
        prod_price=XMLRoute(route='.//ТаблСчФакт/СведТов', attr='ЦенаТов'),
        article=None,
        code=XMLRoute(route='.//ТаблСчФакт/СведТов/ДопСведТов', attr='КодТов'),
        prod_count=XMLRoute(route='.//ТаблСчФакт/СведТов', attr='КолТов'),
    )


class XSD:
    __xsd_pool = 'Не используется по ряду причин'
    __xml_bindings = {
        "upd_xsd.xml": globals().get('UPDRoutesContainer')
    }

    def define_xml(self, xml_path: WindowsPath) -> Union[Torg12RoutesContainer, UPDRoutesContainer, None]:
        """
        Метод определяет тип xml по xsd схеме.
        :param xml_path: Путь до xml
        :return: Union[Torg12RoutesContainer, UPDRoutesContainer]
        """

        for xsd_filename in self.__xsd_pool:

            xsd_file_path = XSD_SCHEMAS_DIR / xsd_filename

            is_valid = self.validate_xml(xsd_file_path=xsd_file_path, xml_file_path=xml_path)

            if is_valid:
                found_class = self.__xml_bindings.get(xsd_filename)
                return found_class()

        return None

    def validate_xml(self, xsd_file_path: WindowsPath, xml_file_path: WindowsPath):
        """
        Метод определяет совпадает xsd схема с xml.
        :param xsd_file_path: Путь до xsd
        :param xml_file_path: Путь до xml
        :return:  True or False
        """

        xmlschema_doc = etree.parse(xsd_file_path)
        xmlschema = etree.XMLSchema(xmlschema_doc)
        xml_doc = etree.parse(xml_file_path)

        return xmlschema.validate(xml_doc)
