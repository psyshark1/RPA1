from logger import log

from business.check_documents_in_edo.check_documents_in_edo import CheckDocumentsInEdo
from business.stage10.create_pzd import ReflectTaskProcessor
from business.stages.stage_1 import Stage1
from business.stages.stage_2 import Stage2
from business.stages.stage_3 import Stage3
from business.stages.stage_4 import Stage4
from business.stages.stage_5 import Stage5
from business.create_inbound_supply_doc.processing import do_processing_create_supply_doc
from business.reflect_214_process.processing import do_processing_reflect_214, complete_operations_reflect_214
from business.reflect_214_process.SAP_Web import Sap
from business.models.db import Procedure
from business.stage11.exec_task import FioriInboxExec
from config import LOGS_DIR, ENV_DATA,EMAIL_SENDER,USER_EMAIL
from db.app_launch_status import AppLaunchStatus
from db.logger import logger
from mail.OWA_MailSender import OWA_MailSender


if __name__ == '__main__':
    logger.set_log('', 'Python', 'main', 'main', 'Info', 'Исполнение', 'Начало работы')
    log.add(level='INFO', dir_path=LOGS_DIR)
    log.info('Исполнение - Начало работы')
    #ls = AppLaunchStatus('ReflectKZ processing')
    #ls.set_start_status_work(ENV_DATA['sap_gui_login'])
    mail = OWA_MailSender('https://mail.megafon.ru', ENV_DATA['mail_login'], ENV_DATA['mail_pass'])
    cnt_r = 0; cnt_g = 0
    procd = Procedure()

    stage1 = Stage1()
    reflecttasks = stage1.get_task()

    stage1 = None; del stage1
    sap_web = None
    web_gui_session = None
    sap_fiori_session = None
    sap_fiori_headers = None
    saved_uuid = None

    for reflecttask in reflecttasks:
        #if reflecttask.number_45 != '4500655042': continue
        stage2 = Stage2(reflecttask, web_gui_session)
        reflecttask = stage2.get_check_data()

        if web_gui_session is None: web_gui_session = stage2.session

        if reflecttask.status != '2':

            stage3 = Stage3(mail, reflecttask, web_gui_session)
            st3 = stage3.get_data_18()

            if st3 == 0:

                stage4 = Stage4(reflecttask, web_gui_session)
                reflecttask = stage4.get_factory()

            if reflecttask.status != '2':
                stage5 = Stage5(reflecttask)
                reflecttask = stage5.get_contractor_data()

                check_docs = CheckDocumentsInEdo(reflecttask)
                reflecttask = check_docs.do_check()

            if (st3 == 7 or st3 == 0) and reflecttask.status != '2':

                if sap_web is None: sap_web = Sap(mail, EMAIL_SENDER, USER_EMAIL, session=web_gui_session, path=stage2.path, ses_token=stage2.ses_token)

                if reflecttask.delivery_type == 1:
                    if do_processing_create_supply_doc(reflecttask,'VL31N', sap_web) == 1:

                        uuid = do_processing_reflect_214(reflecttask, 'MIGO', mail, sap_web, sap_fiori_session, sap_fiori_headers)
                        if sap_fiori_session is None: sap_fiori_session = uuid[1]
                        if sap_fiori_headers is None: sap_fiori_headers = uuid[2]
                        if uuid[0] != '12' and uuid[0] != 'error':
                            if sap_fiori_session is None: sap_fiori_session = uuid[1]

                            ref_task_proc = ReflectTaskProcessor(uuid[0],web_gui_session,reflecttask,EMAIL_SENDER,ENV_DATA['mail_pass'],USER_EMAIL)

                            if ref_task_proc.process():

                                saved_uuid = complete_operations_reflect_214(mail, uuid[0], True, sap_fiori_session, sap_fiori_headers)

                                if saved_uuid != '12' and saved_uuid != '':
                                    result = FioriInboxExec(sap_fiori_session,sap_fiori_headers).exec_task(reflecttask, saved_uuid)
                                    if result > 0: cnt_g += 1
                            else:
                                complete_operations_reflect_214(mail, uuid[0], False, sap_fiori_session,sap_fiori_headers)

                else:

                    uuid = do_processing_reflect_214(reflecttask, 'MIGO', mail, sap_web, sap_fiori_session, sap_fiori_headers)
                    if sap_fiori_session is None: sap_fiori_session = uuid[1]
                    if sap_fiori_headers is None: sap_fiori_headers = uuid[2]
                    if uuid[0] != '12' and uuid[0] != 'error':
                        if sap_fiori_session is None: sap_fiori_session = uuid[1]

                        ref_task_proc = ReflectTaskProcessor(uuid[0],web_gui_session,reflecttask,EMAIL_SENDER,ENV_DATA['mail_pass'],USER_EMAIL)

                        if ref_task_proc.process():

                            saved_uuid = complete_operations_reflect_214(mail, uuid[0], True, sap_fiori_session, sap_fiori_headers)

                            if saved_uuid != '12' and saved_uuid != '':
                                result = FioriInboxExec(sap_fiori_session,sap_fiori_headers).exec_task(reflecttask, saved_uuid)
                                if result > 0: cnt_g += 1
                        else:
                            complete_operations_reflect_214(mail, uuid[0], False, sap_fiori_session, sap_fiori_headers)

        #этап 12
        procd.execute_sql_write(f"UPDATE RPA1079_Tasks SET "
                          f"Status = {reflecttask.status},"
                          f"comment = '{reflecttask.comment}',"
                          f"Exec_date = '{reflecttask.complete_datetime}',"
                          f"Count_EDO = {reflecttask.edo_documents_count} "
                          f"WHERE Num45 = '{reflecttask.number_45}' AND Num18 = '{reflecttask.number_18}'")

        cnt_r += 1

    #ls.set_cnt_request(cnt_r)
    #ls.update_cnt_good(cnt_g)
    #ls.set_end_status_work()

    logger.set_log('', 'Python', 'main', 'main', 'Info', 'Исполнение', 'Штатное завершение работы')
    log.info('Исполнение - Штатное завершение работы')
