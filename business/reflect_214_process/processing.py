from business.models.dto import ReflectTask
from business.reflect_214_process.SAP_Fiori import SapFiori
from config import EMAIL_SENDER, USER_EMAIL, ENV_DATA
from db.logger import logger
from logger import log

def do_processing_reflect_214(reflect:ReflectTask, tr_name:str, mail, sap_web, fiori_session, fiori_headers)-> tuple:

    logger.set_log(reflect.number_45, 'Python', 'processing.py', 'do_payments_processing_reflect_214', 'Info', 'Исполнение', 'Начало работы')
    #log.add(level='INFO', dir_path=LOGS_DIR)
    log.info(f'{reflect.number_45} - Отражение 214 процесса - Начало работы')
    try:
        sap_web.start_transaction(tr_name)
        guid_214 = sap_web.get_214_process(reflect).lower()
        if guid_214 == 'error':
            return (guid_214, None)

        sap_fiori = SapFiori(mail, EMAIL_SENDER, USER_EMAIL, fiori_session, fiori_headers)
        if fiori_session is None: sap_fiori.login(ENV_DATA['sap_fiori_login'],ENV_DATA['sap_fiori_pass'])
        return sap_fiori.reflect_kz(reflect, guid_214)
    except Exception:
        return ('12', None)

def complete_operations_reflect_214(mail, uuid:str, save:bool, fiori_session, fiori_headers)-> str:
    try:
        sap_fiori = SapFiori(mail, EMAIL_SENDER, USER_EMAIL, fiori_session, fiori_headers)
        if fiori_session is None: sap_fiori.login(ENV_DATA['sap_fiori_login'], ENV_DATA['sap_fiori_pass'])
        if save:
            return sap_fiori.save_proc(uuid)
        else:
            return  sap_fiori.cancel_proc(uuid)
    except Exception:
        return '12'
