import datetime
from pathlib import WindowsPath
from typing import List
from sap_web import FioriBase, HttpData, HttpMethod
import requests

from business.models.dto import ReflectTask, IncomingDocument
from business.utils import decode_date
from config import ENV_DATA, TEMP_DIR


class FioriMain(FioriBase):

    def __init__(self):
        super().__init__(headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          'Chrome/85.0.4183.121 Safari/537.36',
            'Accept': 'application/json'
        })


class FioriIncomingDocuments:
    """Фиори вкладка Inbox входящие электронные документы"""

    def __init__(self, fiori: FioriMain):
        self.__fiori = fiori

    def get_incoming_documents(self, task: ReflectTask) -> List[IncomingDocument]:
        """
        Метод получает входящие документы со вкладки Inbox входящие документы.
        Эмулирует установкуу фильтра и нажатие кнопки "Применить"
        :return:
        """

        filter_str = '%20or%20'.join(tuple(map(lambda n: f'DocumentShpNr%20eq%20%27{n}%27', task.edo_numbers)))

        http_data = HttpData(
            method=HttpMethod.GET,
            url=f'sap/opu/odata/ccpm/DOC_INBOX_MNG_SRV/xCCPMxAPDIN_C_DOCUMENT_V2/',
            params=f"sap-client={self.__fiori.CLIENT}$skip=0&$top=45&$orderby=DocumentID%20desc&$filter=({filter_str})&"
                   f"$select=DocumentShpNr%2cDocumentID%2cCompanyCode%2cto_CompanyCode%2fCompanyCodeName%2cDocumentBranchId%2c"
                   f"BranchNameLong%2cCCPMCreationDate%2cCCPMCreationTime%2cBusPart%2cBusinessPartner%2cBPName%2cDocumentType%2cto_DocumentType%2f"
                   f"DocumentType_Text%2cDocumentOEDDocTyp%2cto_OEDDocType%2fOEDDocTyp_Text%2cSendStatus%2cSendStatusText%2cOEDPoName%2c"
                   f"DocumentInitiator%2cVersionPartnerComment%2cprocessid%2cFileName%2cDocumentUUID%2cAttachedToProcess&$expand=to_CompanyCode%2c"
                   f"to_DocumentType%2cto_OEDDocType&$inlinecount=allpages",

        )

        resp = self.__fiori.send_request(http_data)

        documents = resp.json().get('d').get('results')

        return list(map(lambda doc_data: IncomingDocument(data=doc_data), documents))

    def download_document(self, document: IncomingDocument) -> WindowsPath:
        """
        Метод скачивает документ из Сап фиора.
        :param document: Документ, который нужно скачать
        :return: Путь до файла
        """

        file_content, filename = self.__download_file(document.doc_id)

        # Формируем путь сохранения и сохраняем файл
        save_path = TEMP_DIR / filename

        try:
            with open(save_path, 'w+b') as file:
                file.write(file_content)
        except:
            raise Exception(f'%s. Не удалось сохранить файл {document.filename}.' % self.download_document.__qualname__)

        return WindowsPath(save_path)

    def __download_file(self, doc_id: str) -> tuple:
        """
        Метод отправляет запрос наскачивание XML и возвращает путь для скачивания
        :param doc_id: id документа, который нужно скачать
        :return: (<байтовый массив файла>, <имя файла>)
        """

        # Отправляем запрос на получение ссылки на скачивание файла
        http_data = HttpData(
            method=HttpMethod.POST,
            url=f'sap/opu/odata/ccpm/DOC_INBOX_MNG_SRV/DownloadXML',
            params=f"sap-client={self.__fiori.CLIENT}&DocumentID='{doc_id}'",

        )

        resp = self.__fiori.send_request(http_data)

        try:
            download_url = resp.json().get('d').get('DownloadXML').get('URL')
        except AttributeError:
            raise Exception('%s. Не удалось получить ссылку для скачивания XML.' % self.__download_as_xml.__qualname__)

        # Отправляем запрос на получение файла
        xml_file_response = requests.get(url=download_url, verify=False)

        if xml_file_response.status_code != 200:
            raise requests.HTTPError(f'%s. Response code: {xml_file_response.status_code}\n Не удалось получить XML файл.' % self.__download_as_xml.__qualname__)

        try:
            filename = xml_file_response.headers.get('Content-Disposition').split('filename=')[1]
        except IndexError:
            raise Exception('%s. Не удалось получить имя файла.' % self.__download_as_xml.__qualname__)

        return bytearray(xml_file_response.content), filename

    def __download_as_pdf(self, doc_id: str) -> tuple:
        """
        TODO: Реализовать как буцдет подходящий пример
        Метод отправляет запрос наскачивание PDF и возвращает путь для скачивания
        :param doc_id: id документа, который нужно скачать
        :return: (<байтовый массив файла>, <имя файла>)
        """
        pass


class FioriSearchForProcessesToChangeContracts:
    """Фиори вкладка Поиск процессов по изменению договоров(ЕКД)"""

    def __init__(self, fiori: FioriMain):
        self.__fiori = fiori

    def get_document_date(self, internal_number: str) -> datetime:
        """
        Метод получает Дату документа. Пункт 6.8.с.ix
        :param internal_number: внутреннеий номер ДС, полученный в ВЕБГУЕ. Пункт 6.8.с.ii
        :return: Дату документа
        """

        found_process = self.__search_by_internal_number_ds(internal_number=internal_number)

        unicode_date = found_process.get('ProcessStartDate')

        if not unicode_date:
            raise AttributeError('%s. Не удалось получить Дату договора' % self.get_document_date.__qualname__)

        try:
            return decode_date(unicode_date)
        except AttributeError:
            raise AttributeError('%s. Не удалось конвертировать дату из: %s' % (self.get_document_date.__qualname__, unicode_date))

    def get_document_as_pdf(self, internal_number: str) -> WindowsPath:
        """
        Метод получает пдф документ заказа
        :param internal_number: внутреннеий номер ДС, полученный в ВЕБГУЕ. Пункт 6.8.с.ii
        :return:
        """

        found_process = self.__search_by_internal_number_ds(internal_number=internal_number)

        contract_uuid = found_process.get('ContractUUID')

        if not contract_uuid:
            raise AttributeError('%s. Не удалось получить uuid договора' % self.get_document_as_pdf.__qualname__)

        file_uuid, version_uuid = self.__get_file_for_approval_sfile_uuid(contract_uuid=contract_uuid)

        saved_file_path = self.__download_file_to_approval(file_uuid, version_uuid)

        return saved_file_path

    def __get_file_for_approval_sfile_uuid(self, contract_uuid: str) -> tuple:
        """
        Метод получает DocumentUUID и VersionUUID файла для согласования(SFILE) с вкладки "Документы" для дальнгейшего скачивания
        :param contract_uuid: юид найденого контракта
        :return: uuid файла для согласования(SFILE)
        """

        http_data = HttpData(
            method=HttpMethod.GET,
            url=f"sap/opu/odata/ccpm/ADAGREEMENT_MNG_SRV/xCCPMxAPPRC_C_PrcAdAgr(ContractUUID=guid'%s',IsActiveEntity=true)/to_ContractDocumentWD" % contract_uuid,
        )

        resp = self.__fiori.send_request(http_data)

        try:
            file_list = resp.json()['d']['results']
            file_for_approval_list = list(filter(lambda file: file.get('DocTypeName') == 'Файл для согласования' and file.get('DocumentType') == 'SFILE', file_list))

            if len(file_for_approval_list) > 1:
                raise Exception('%s. В списке файлов присутствует несколько файлов для согласования' % self.__get_file_for_approval_sfile_uuid.__qualname__)

            file_for_approval = file_for_approval_list[0]

            return file_for_approval.get('DocumentUUID'), file_for_approval.get('VersionUUID')
        except KeyError:
            raise Exception('%s. Не удалось получить список файлов' % self.__get_file_for_approval_sfile_uuid.__qualname__)
        except IndexError:
            raise Exception('%s. В списке файлов нет файла для согласования' % self.__get_file_for_approval_sfile_uuid.__qualname__)

    def __download_file_to_approval(self, file_uuid: str, version_uuid: str) -> WindowsPath:
        """
        Мектод скачивает файл для согласования
        :param file_uuid: uuid файла
        :param file_uuid: uuid версии
        :return: путь до файла
        """
        http_data = HttpData(
            method=HttpMethod.GET,
            url=f"sap/opu/odata/CCPM/DOCUMENT_ATF_SRV/AttachmentSet(DocumentUUID=guid'%s',VersionUUID=guid'%s',"
                f"ProcessUUID=guid'00000000-0000-0000-0000-000000000000',ContractUUID=guid'00000000-0000-0000-0000-000000000000',DocumentUUIDList='',VersionUUIDList='',ObjectUUIDList='',ApplName='',SelAttr='')/$value" % (file_uuid, version_uuid),
        )

        resp = self.__fiori.send_request(http_data)

        file_bytes = resp.content

        if not file_bytes:
            raise requests.HTTPError(f'%s. Не удалось получить файл.' % self.__download_file_to_approval.__qualname__)

        try:
            filename = resp.headers.get('Content-Disposition').split('filename*=UTF-8\'\'')[1]
        except IndexError:
            raise Exception('%s. Не удалось получить имя файла.' % self.__download_file_to_approval.__qualname__)

        # Формируем путь сохранения и сохраняем файл
        save_path = TEMP_DIR / filename

        try:
            with open(save_path, 'w+b') as file:
                file.write(bytearray(file_bytes))
        except:
            raise Exception(f'%s. Не удалось сохранить файл {filename}.' % self.__download_file_to_approval.__qualname__)

        return WindowsPath(save_path)

    def __search_by_internal_number_ds(self, internal_number: str):
        """
        Метод осуществляет поиск процессов изменения договора по внутреннему номеру ДС
        :param internal_number: внутреннеий номер ДС, полученный в ВЕБГУЕ
        :return:
        """

        http_data = HttpData(
            method=HttpMethod.GET,
            url=f'sap/opu/odata/ccpm/ADAGREEMENT_MNG_SRV/xCCPMxAPPRC_C_PrcAdAgr/',
            params=f"sap-client={self.__fiori.CLIENT}&$skip=0&$top=25&$orderby=ProcessID%20desc&"
                   f"$filter=((ContractInternalID%20eq%20%27{internal_number}%27)%20and%20(IsActiveEntity%20eq%20false%20or%20SiblingEntity/IsActiveEntity%20eq%20null))"
                   f"&$select=IsFavorite_%2cContractResume%2cProcessID%2cProcessType%2cto_ProcessType%2fProcessType_Text%2cProcessStartDate%2cProcessStatus%2c"
                   f"to_ProcessStatusVH%2fStatusName%2cPartnersList%2cContractName%2cContractInternalID%2cContractUUID%2cIsActiveEntity%2cHasDraftEntity%2c"
                   f"HasActiveEntity%2cContractResume_fc%2cContractName_fc%2cDraftAdministrativeData%2cHigherContractUUID&$expand=to_ProcessType%2c"
                   f"to_ProcessStatusVH%2cDraftAdministrativeData&$inlinecount=allpages"

        )

        resp = self.__fiori.send_request(http_data)

        try:
            return resp.json()['d']['results'][0]
        except Exception:
            raise Exception('%s. Не удалось найти Процесс по номеру %s', (self.__search_by_internal_number_ds.__qualname__, internal_number))


if __name__ == '__main__':
    fiori = FioriMain()
    fiori.login(login=ENV_DATA['fiori_login'], password=ENV_DATA['fiori_password'])
    t = FioriSearchForProcessesToChangeContracts(fiori)

    t.get_document_as_pdf('100000001745447')
