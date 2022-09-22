import datetime
import os
import re
import time

from sap_web.fiori.fiori_process import FioriProcess
from sap_web.fiori.fiori_inbox import FioriInbox
from mail.OWA_MailSender import OWA_MailSender
from business.models.dto import ReflectTask
from sap_web.models import HttpMethod, HttpData
from logger import log
from db.logger import logger
from pdfminer.high_level import extract_text
from config import TEMP_DIR, TEMP_DOC, MONTHS

class SapFiori(FioriInbox):

    def __init__(self, mail:OWA_MailSender, m_from, m_to, session, headers):
        self.mail = mail
        self.mail_from = m_from
        self.mail_to = m_to
        super().__init__(session=session, headers=headers)

    def reflect_kz(self, reflect:ReflectTask, guid:str)-> tuple:
        docs = self.get_inbox_data()
        chk_inbox = False
        for doc in docs:
            if doc.get('processuuid') == guid:
                chk_inbox = True; break

        if chk_inbox:
            fiori_proc = FioriProcess(session=self.session, headers=self.get_headers())
            r = fiori_proc.edit_process(guid)

            log.info(f'{reflect.number_45} - Заполнение процесса по отражению КЗ (214*) - Обработка {reflect.number_214} - {reflect.number_214} взят в работу')
            logger.set_log(f'{reflect.number_45}', 'SAP Fiori', 'reflect_214_process', 'reflect_kz', 'Info', f'Обработка {reflect.number_214}', f'{reflect.number_214} взят в работу')

            if r[0]:
                signers = fiori_proc.get_signers(r[1].get('ProcessUUID'), True)

                if len(signers) == 0:
                    sign = fiori_proc.add_signer(r[1].get('ProcessUUID'))

                    fiori_proc.update_signer(sign.get('ProcessSignatoryUUID'),{'ProcessSignatoryUser': f'{reflect.contractor.subscriber}'})

                else:

                    for signer in signers:
                        if signer.get('ProcessSignatoryUser') != str(reflect.contractor.subscriber):
                            fiori_proc.update_signer(signer.get('ProcessSignatoryUUID'),{'ProcessSignatoryUser': f'{reflect.contractor.subscriber}'})

                e_docs = self.find_electronic_docs(reflect.edo_numbers)

                if len(e_docs) == reflect.edo_documents_count:

                    for e_doc in e_docs:

                        fiori_proc.add_electronic_doc(r[1].get('ProcessUUID'), e_doc.get('DocumentUUID'))

                elif len(e_docs) == 0:

                    log.error(f'{reflect.number_45} - Заполнение процесса по отражению КЗ (214*) - Ошибка поиска пакета документов {reflect.number_214} - Пакеты докуменов не найдены')
                    logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'reflect_kz', 'Error',
                                   f'Ошибка поиска пакета документов {reflect.number_214}',
                                   f'Пакеты докуменов не найдены')
                    self.mail.send_mail(self.mail_from, self.mail_to, 'Ошибка ЭДО RPA-1079',f'По заданию ИД {reflect.id} № {reflect.number_45} Пакеты докуменов не найдены')
                    reflect.status = '2'
                    reflect.comment = reflect.comment + f'{reflect.number_214} Пакеты докуменов не найдены;'
                    fiori_proc.save_process(r[1].get('ProcessUUID'))
                    return ('12', self.session, self.get_headers())

                elif len(e_docs) != reflect.edo_documents_count:

                    log.error(f'{reflect.number_45} - Заполнение процесса по отражению КЗ (214*) - Ошибка поиска пакета документов {reflect.number_214} - Не совпадает количество документов при отражении КЗ')
                    logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'reflect_kz', 'Error',f'Ошибка поиска пакета документов {reflect.number_214}',f'Не совпадает количество документов при отражении КЗ')
                    self.mail.send_mail(self.mail_from, self.mail_to, 'Ошибка ЭДО RPA-1079',f'По заданию ИД {reflect.id} № {reflect.number_45} Не совпадает количество документов при отражении КЗ')
                    reflect.status = '2'
                    reflect.comment = reflect.comment + f'{reflect.number_214} Не совпадает количество документов при отражении КЗ;'
                    fiori_proc.save_process(r[1].get('ProcessUUID'))
                    return ('12', self.session, self.get_headers())

                added_e_docs = fiori_proc.get_docs(r[1].get('ProcessUUID'),True)

                for added_e_doc in added_e_docs:
                    if added_e_doc.get('DocumentType') == 'UNIDENT':
                        self.download_doc(r[1].get('ContractUUID'), added_e_doc.get('DocumentUUID'), added_e_doc.get('VersionUUID'), str(TEMP_DIR) + '\\' + TEMP_DOC)
                        pdf_cont = extract_text(str(TEMP_DIR) + '\\' + TEMP_DOC)
                        os.remove(str(TEMP_DIR) + '\\' + TEMP_DOC)

                        e_doc_data = self.__pdf_parsing(pdf_cont)

                        for key, value in e_doc_data.items():
                            fiori_proc.update_doc(added_e_doc.get('ProcessDocUUID'), {'DocumentType': key})
                            fiori_proc.update_doc(added_e_doc.get('ProcessDocUUID'), {'VersionDocNumber': value[0]})
                            fiori_proc.update_doc(added_e_doc.get('ProcessDocUUID'), {'VersionDateTime':f'\/Date({str(value[1])})\/'})

                #result = fiori_proc.save_process(r[1].get('ProcessUUID'))
                log.info(f'{reflect.number_45} - Заполнение процесса по отражению КЗ (214*) - Обработка {reflect.number_214} - {reflect.number_214} подготовлен')
                logger.set_log(f'{reflect.number_45}', 'SAP Fiori', 'reflect_214_process', 'reflect_kz', 'Info', f'Обработка {reflect.number_214}', f'{reflect.number_214} подготовлен')
                return (r[1].get('ProcessUUID'), self.session, self.get_headers())

            else:

                log.error(f'{reflect.number_45} - Заполнение процесса по отражению КЗ (214*) - Ошибка редактирования {reflect.number_214} - {reflect.number_214} невозможно взять в работу')
                logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'reflect_kz', 'Error',f'Ошибка редактирования {reflect.number_214}',f'{reflect.number_214} невозможно взять в работу')
                self.mail.send_mail(self.mail_from, self.mail_to, 'Ошибка ЭДО RPA-1079', f'По заданию ИД {reflect.id} № {reflect.number_45} Не удалось взять в работу {reflect.number_214}')
                reflect.status = '2'
                reflect.comment = reflect.comment + f'{reflect.number_214} процесс не удалось взять в работу;'
                return ('12', self.session, self.get_headers())

        log.error(f'{reflect.number_45} - Заполнение процесса по отражению КЗ (214*) - Ошибка поиска {reflect.number_214} - {reflect.number_214} отсутствует во входящих CCPM')
        logger.set_log(f'{reflect.number_45}', 'SAP', 'reflect_214_process', 'reflect_kz', 'Error', f'Ошибка поиска {reflect.number_214}', f'{reflect.number_214} отсутствует во входящих CCPM')
        self.mail.send_mail(self.mail_from,self.mail_to,'Ошибка ЭДО RPA-1079',f'По заданию ИД {reflect.id} № {reflect.number_45} Отсутствует 214 в FIORI {reflect.number_214}')
        reflect.status = '2'
        reflect.comment = reflect.comment + f'{reflect.number_214} процесс отсутствует во входящих CCPM;'
        return ('12', self.session, self.get_headers())

    def save_proc(self, processUUID)-> str:
        fiori_proc = FioriProcess(session=self.session, headers=self.get_headers())
        result = fiori_proc.save_process(processUUID)
        return result[1].get('ProcessUUID')

    def cancel_proc(self, processUUID)-> str:
        fiori_proc = FioriProcess(session=self.session, headers=self.get_headers())
        fiori_proc.delete_process_draft(processUUID)
        return "canceled"

    def find_electronic_docs(self, numbers: list, select: tuple = None) -> list:

        query = ' or '.join([f"DocumentShpNr eq '{n}'" for n in numbers])
        fields = '' if not select else ',' + ','.join(select)

        http_data = HttpData(
            method=HttpMethod.GET,
            url='sap/opu/odata/ccpm/DOC_INBOX_MNG_SRV/xCCPMxAPDIN_C_DOCUMENT_V2',
            params={
                'sap-client': self.CLIENT,
                '$filter': f"(({query}) and UserRegime eq '2')",
                '$select': 'DocumentShpNr,DocumentID,CompanyCode,to_CompanyCode/CompanyCodeName,DocumentBranchId,'
                           'BranchNameLong,CCPMCreationDate,CCPMCreationTime,BusPart,BusinessPartner,BPName,'
                           'DocumentType,to_DocumentType/DocumentType_Text,DocumentOEDDocTyp,to_OEDDocType/'
                           'OEDDocTyp_Text,SendStatus,SendStatusText,OEDPoName,DocumentInitiator,'
                           'VersionPartnerComment,processid,FileName,DocumentUUID,DocumentUUID,IdOed,'
                           f'VersionLinkUUID,VersionUUID,DocumentShpNr,DocumentDirection{fields}',
                '$expand': 'to_CompanyCode,to_DocumentType,to_OEDDocType'
            }
        )

        self._headers['Accept'] = 'application/json'

        resp = self.send_request(http_data)
        self.clear_headers()
        return resp.json()['d']['results']

    def __pdf_parsing(self, pdf_c:str)-> dict:

        if pdf_c != '\f':

            if re.search(r'Счет на оплату', pdf_c, flags=re.IGNORECASE):

                r = re.findall(r'Счет на оплату\s№(?:\s|)(\S{1,15}?)\sот\s(\d{2}\.\d{2}\.\d{4}|\d{1,2}\s[А-Яа-я]{3,8}\s\d{4})', pdf_c, flags=re.IGNORECASE)

                if len(r) != 0:
                    return {'PAYBILL': (r[0][0], self.__date_converter(r[0][1]))}
                return {'PAYBILL': ('БН', self.__date_converter(datetime.datetime.today().strftime('%d.%m.%Y')))}

            elif re.search(r'акт ', pdf_c, flags=re.IGNORECASE):

                r = re.findall(r'акт[\s\S]+?№(?:\s|)(\S{1,15}?)\sот\s(\d{2}\.\d{2}\.\d{4}|\d{1,2}\s[А-Яа-я]{3,8}\s\d{4})', pdf_c, flags=re.IGNORECASE)

                if len(r) != 0:
                    return {'ACTPP': (r[0][0], self.__date_converter(r[0][1]))}
                return {'ACTPP': ('БН', self.__date_converter(datetime.datetime.today().strftime('%d.%m.%Y')))}

        return {'OTHER': ('БН', self.__date_converter(datetime.datetime.today().strftime('%d.%m.%Y')))}

    def __date_converter(self, date:str)-> int:

        for key, value in MONTHS.items():
            if date.lower().find(value) != -1:
                date = date.replace(f' {value} ',f'.{key}.')
                break

        date = datetime.datetime.strptime(date, "%d.%m.%Y").date()
        d = datetime.datetime(date.year, date.month, date.day, 4, 0)
        return int(time.mktime(d.timetuple()) * 1000)
