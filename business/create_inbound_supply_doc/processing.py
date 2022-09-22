from business.models.dto import ReflectTask
from db.logger import logger
from logger import log

def do_processing_create_supply_doc(reflect:ReflectTask,tr_name:str, sap_web)-> int:

    #logger.set_log(f'{reflect.number_45}', 'Python', 'main.py', 'do_payments_processing', 'Info', 'Исполнение', 'Начало работы')
    #log.add(level='INFO', dir_path=LOGS_DIR)
    log.info(f'{reflect.number_45} - Создание документа входящей поставки - Начало работы')
    try:
        sap_web.start_transaction(tr_name)
        return sap_web.get_inbound_supply_doc(reflect)
    except Exception as err:
        log.info(f'{reflect.number_45} - Создание документа входящей поставки - Ошибка SAP {str(err)}')
        logger.set_log(f'{reflect.number_45}', 'Python', 'main.py', 'do_processing_create_supply_doc', 'Error', 'Исполнение', f'''Ошибка SAP {str(err).replace("'","")}''')
        return -1
