from sap_web import WebGuiBase, HttpMethod, HttpData
#from loguru import logger


class BaseAdditions(WebGuiBase):
    """Класс с вспомогательными методами запросов"""

    def __init__(self, session=None):
        """
        Конструктор

        :param session: (Опционально) Объект сессии
        """

        super(BaseAdditions, self).__init__(base_url='http://sap-rio.megafon.ru', session=session)

    #@logger.catch()
    def send_template_request(self, json):
        """
        Отправляет запросы со статическим payload

        Payload:
            method=HttpMethod.POST,\n
            url=f'{self.path}/batch/json',\n
            params={
                '~RG_WEBGUI': 'X',\n
                'sap-statistics': 'true',\n
                '~SEC_SESSTOKEN': self._ses_token}

        :param json: JSON из запроса
        :return: JSON ответа
        """

        return self.__send_template_request(json)

    #@logger.catch()
    def open_transaction(self, transaction: str, tr_settings:bool = False):
        """
        Открывает указанныую транзакцию.

        :param transaction: Название транзакции
        :return: Ответ сервера
        """

        response = self.__send_template_request(
            json=[
                {"content": transaction, "post": "okcode/ses[0]"},
                {"post": "vkey/0/ses[0]"},
                {"get": "state/ur"}
            ], tr_settings=tr_settings)

        return response

        # self.__send_template_request(
        #     json=[
        #         {"post": "vkey/71/wnd[0]"},
        #         {"get": "state/ur"}
        #     ]
        # )
        #
        # self.__send_template_request(
        #     json=[
        #         {"post": "value/wnd[1]/usr/txt130_FIND", "content": f"{transaction}", "logic": "ignore"}
        #     ]
        # )

        # return self.__send_template_request(
        #     json=[
        #         {"content": f"{transaction}", "post": "value/wnd[1]/usr/txt130_FIND"},
        #         {"post": "action/304/wnd[1]/usr/txt130_FIND", "content": f"position={len(transaction)}",
        #          "logic": "ignore"},
        #         {"post": "focus/wnd[1]/usr/txt130_FIND", "logic": "ignore"},
        #         {"post": "vkey/0/ses[0]"},
        #         {"get": "state/ur"}
        #     ]
        # )

    #@logger.catch()
    def __send_template_request(self, json, tr_settings:bool = False):
        """
        Отправляет запросы со статическим payload

        :param json: JSON из запроса
        :return: JSON ответа
        """
        if tr_settings:
            http_data = HttpData(
                method=HttpMethod.POST,
                url=f'{self.path}/batch/json',
                params={
                    '~RG_WEBGUI': 'X',
                    'sap-statistics': 'true',
                    '~path': f'/{self._path}',
                    'SEC_SESSTOKEN': self._ses_token,
                    '~SEC_SESSTOKEN': self._ses_token,
                    '~transaction': '',
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
                    '~ci_result': '~webguiUserAreaHeight=2003;~webguiUserAreaWidth=3920;~webguiScreenWidth=4096;~webguiScreenHeight=2160;ThemedScrollbarDimension=12',
                    '~SEC_SESSTOKEN': self._ses_token
                },
                json=json
            )
        else:
            http_data = HttpData(
                method=HttpMethod.POST,
                url=f'{self.path}/batch/json',
                params={
                    '~RG_WEBGUI': 'X',
                    'sap-statistics': 'true',
                    '~SEC_SESSTOKEN': self._ses_token,
                    'SEC_SESSTOKEN': self._ses_token,
                    '~path': f'/{self._path}',
                },
                json=json
            )

        response = self.send_request(http_data)
        return response.json()
