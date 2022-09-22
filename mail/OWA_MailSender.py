import base64
import json
import os
import re

import requests
from requests.auth import HTTPBasicAuth


class OWA_MailSender():
    def __init__(self, urlMail, login, passw):
        self.url = urlMail
        self.mailHeaders = {'Connection': 'keep-alive'}
        self.mailHeaders['User-Agent'] = 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36'
        if self.url.find('https') != -1:
            self.mailHeaders['Host'] = self.url.replace('https://', '')
        else:
            self.mailHeaders['Host'] = self.url.replace('http://', '')
        self.mailHeaders['Origin'] = self.url
        self.mailHeaders['Accept'] = '*/*'
        self.mailHeaders['Sec-Fetch-Dest'] = 'empty'
        self.mailHeaders['Sec-Fetch-Mode'] = 'cors'
        self.mailHeaders['Sec-Fetch-Site'] = 'same-origin'
        self.url = urlMail + '/owa/'
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(login, passw)
        self.item_id = None
        self.change_key = None
        self.body_html = (
            '<HTML><head><meta http-equiv=\\"Content-Type\\" content=\\"text/html; charset=UTF-8\\"><style type=\\"text/css\\" style=\\"display:none;\\"></style></head>'
            '<Body dir=\\"ltr\\"><div id=\\"divtagdefaultwrapper\\" style=\\"font-size:12pt;color:#000000;background-color:#FFFFFF;font-family:Calibri,Arial,Helvetica,sans-serif;\\" dir=\\"ltr\\"><p>',
            '</p></div></Body></HTML>')


    def __autoriz(self) -> bool:
        '''Авторизация'''
        if self.mailHeaders.get('Content-Type') is not None:
            self.mailHeaders.pop('Content-Type')
        if self.mailHeaders.get('X-Requested-Withe') is not None:
            self.mailHeaders.pop('X-Requested-With')

        r = self.session.get(self.url, headers=self.mailHeaders,verify=False)

        if r.status_code != 200:
            return False

        self.__get_canary()
        query = (('ns','PendingRequest'),('ev','FinishNotificationRequest'),('UA','0'))
        r = self.session.post(self.url + '/ev.owa2?ns=PendingRequest&ev=FinishNotificationRequest&UA=0', data=query, headers=self.mailHeaders)

        if r.status_code != 200:
            return False

        js = json.loads(r.text)
        self.mailHeaders['cid'] = js['cid']
        self.__get_canary()

        return True

    def __get_canary(self):
        self.mailHeaders['X-OWA-CANARY'] = self.session.cookies['X-OWA-CANARY']

    def __set_action_headers(self, action, x_owa_action_name, id):
        '''Установка Action-заголовков в запросе'''
        self.mailHeaders['Action'] = action
        self.mailHeaders['X-OWA-ActionId'] = '-' + str(id)
        self.mailHeaders['X-OWA-ActionName'] = x_owa_action_name
        self.__get_canary()

    def __attach_to_base64(self, mAttachPath) -> str:
        '''Преобразование файла-вложения в строку base64'''
        f = open(mAttachPath, 'rb')
        b64 = base64.b64encode(f.read()).decode('utf-8')
        f.close(); del f
        return b64

    def __get_mail_props(self, response_text:str, attach=False) -> bool:
        '''Получение id и key созданного сообщения'''
        js = json.loads(response_text)
        try:
            if attach:
                self.change_key = js['Body']['ResponseMessages']['Items'][0]['Attachments'][0]['AttachmentId']['RootItemChangeKey']
                self.item_id = js['Body']['ResponseMessages']['Items'][0]['Attachments'][0]['AttachmentId']['RootItemId']
            else:
                self.change_key = js['Body']['ResponseMessages']['Items'][0]['Items'][0]['ItemId']['ChangeKey']
                self.item_id = js['Body']['ResponseMessages']['Items'][0]['Items'][0]['ItemId']['Id']
        except:
            return False
        return True

    def __get_recipients(self, mTo):
        '''Проверка установка email получателей в запрос на отправку письма'''
        rcp = []
        for to in mTo:
            r = re.findall(r'([a-z0-9_\.-]+?@[a-z0-9_\.-]+?\.[a-z]{2,20}(?:\.[a-z]{2,15}|)(?:\.[a-z]{2,15}|))', to, flags=re.IGNORECASE)
            if len(r) != 0:
                rcp.append({"MailboxType":"Mailbox","RoutingType":"SMTP","EmailAddress":r[0],"Name":r[0]})
        return rcp

    def __get_attachments(self, mAttachPath):
        '''Установка вложений в запрос на отправку письма'''
        atp = []
        for attp in mAttachPath:
            fname = os.path.basename(attp)
            size = os.path.getsize(attp)
            b64 = self.__attach_to_base64(attp)

            atp.append({"__type":"FileAttachment:#Exchange","Content":b64,"IsContactPhoto":"false","ContentType":"application/x-www-form-urlencoded","IsInline":"false",
            "Name":fname,"Size":size})
        return atp


    def send_mail(self, mFrom: str, mTo: tuple, mSubj: str, mText:str, mAttachPath=None) -> bool:
        '''Метод отправки сообщения'''
        if self.mailHeaders.get('cid') is None:
            if not self.__autoriz():
                return False

        id = 1

        query = {"__type":"CreateItemJsonRequest:#Exchange","Header":{"__type":"JsonRequestHeaders:#Exchange","RequestServerVersion":"V2015_10_15",
                "TimeZoneContext":{"__type":"TimeZoneContext:#Exchange","TimeZoneDefinition":{"__type":"TimeZoneDefinitionType:#Exchange","Id":"Caucasus Standard Time"}}},
                "Body":{"__type":"CreateItemRequest:#Exchange","Items":[{"__type":"Message:#Exchange","Subject":mSubj,"Body":{"__type":"BodyContentType:#Exchange","BodyType":"HTML","Value":self.body_html[0]+mText+self.body_html[1]},
                "Importance":"Normal","From":{"__type":"SingleRecipientType:#Exchange","Mailbox":{"MailboxType":"Mailbox","RoutingType":"SMTP","EmailAddress":mFrom}},
                "ToRecipients":[],"CcRecipients":[],"BccRecipients":[],"Sensitivity":"Normal","IsDeliveryReceiptRequested":"false","IsReadReceiptRequested":"false"}],"ClientSupportsIrm":"true","OutboundCharset":"AutoDetect",
                "MessageDisposition":"SaveOnly","ComposeOperation":"newMail"}}

        recipients = self.__get_recipients(mTo)
        if len(recipients) == 0: return False

        query['Body']['Items'][0]['ToRecipients'] = recipients

        if self.mailHeaders.get('Content-Type') is None:
            self.mailHeaders['Content-Type'] = 'application/json; charset=UTF-8'
        if self.mailHeaders.get('X-Requested-With') is None:
            self.mailHeaders['X-Requested-With'] = 'XMLHttpRequest'
        self.__set_action_headers('CreateItem', 'CreateMessageForCompose', id)

        r = self.session.post(self.url + 'service.svc?action=CreateItem&ID=-' + str(id) + '&AC=1', json=query, headers=self.mailHeaders)

        if r.status_code != 200:
            return False

        if not self.__get_mail_props(r.text):
            return False

        id += 1

        if mAttachPath is not None:

            query = {"__type":"CreateAttachmentJsonRequest:#Exchange","Header":{"__type":"JsonRequestHeaders:#Exchange","RequestServerVersion":"Exchange2013",
            "TimeZoneContext":{"__type":"TimeZoneContext:#Exchange","TimeZoneDefinition":{"__type":"TimeZoneDefinitionType:#Exchange","Id":"Caucasus Standard Time"}}},
            "Body":{"__type":"CreateAttachmentRequest:#Exchange","ParentItemId":{"__type":"ItemId:#Exchange","Id":self.item_id,"ChangeKey":self.change_key},
            "Attachments":[],"RequireImageType":"false","IncludeContentIdInResponse":"false","ClientSupportsIrm":"true","CancellationId":"null"}}

            query['Body']['Attachments'] = self.__get_attachments(mAttachPath)

            self.__set_action_headers('CreateAttachmentFromLocalFile', 'CreateAttachmentFromLocalFile', id)

            r = self.session.post(self.url + 'service.svc?action=CreateAttachmentFromLocalFile&ID=-' + str(id) + '&AC=1', json=query, headers=self.mailHeaders)

            if r.status_code != 200:
                return False

            if not self.__get_mail_props(r.text, True):
                return False

            id += 1

        query = {"__type":"UpdateItemJsonRequest:#Exchange","Header":{"__type":"JsonRequestHeaders:#Exchange","RequestServerVersion":"Exchange2015",
        "TimeZoneContext":{"__type":"TimeZoneContext:#Exchange","TimeZoneDefinition":{"__type":"TimeZoneDefinitionType:#Exchange","Id":"Caucasus Standard Time"}}},
        "Body":{"__type":"UpdateItemRequest:#Exchange","ItemChanges":[{"__type":"ItemChange:#Exchange",
        "Updates":[{"__type":"DeleteItemField:#Exchange","Path":{"__type":"ExtendedPropertyUri:#Exchange","PropertyId":35356,"DistinguishedPropertySetId":"Sharing","PropertyType":"CLSID"}},
        {"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"From"},"Item":{"__type":"Message:#Exchange",
        "From":{"__type":"SingleRecipientType:#Exchange","Mailbox":{"MailboxType":"Mailbox","RoutingType":"SMTP","EmailAddress":mFrom}}}},
        {"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"CcRecipients"},
        "Item":{"__type":"Message:#Exchange","CcRecipients":[]}},{"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"BccRecipients"},
        "Item":{"__type":"Message:#Exchange","BccRecipients":[]}},{"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"ToRecipients"},
        "Item":{"__type":"Message:#Exchange","ToRecipients":[]}},
        {"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"IsReadReceiptRequested"},"Item":{"__type":"Message:#Exchange","IsReadReceiptRequested":"false"}},
        {"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"IsDeliveryReceiptRequested"},"Item":{"__type":"Message:#Exchange","IsDeliveryReceiptRequested":"false"}},
        {"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"Subject"},"Item":{"__type":"Message:#Exchange","Subject":mSubj}},
        {"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"Importance"},"Item":{"__type":"Message:#Exchange","Importance":"Normal"}},
        {"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"Body"},"Item":{"__type":"Message:#Exchange",
        "Body":{"__type":"BodyContentType:#Exchange","BodyType":"HTML","Value":self.body_html[0]+mText+self.body_html[1]}}},{"__type":"SetItemField:#Exchange","Path":{"__type":"PropertyUri:#Exchange","FieldURI":"Sensitivity"},
        "Item":{"__type":"Message:#Exchange","Sensitivity":"Normal"}}],"ItemId":{"__type":"ItemId:#Exchange","Id":self.item_id,"ChangeKey":self.change_key}}],
        "ConflictResolution":"AlwaysOverwrite","ClientSupportsIrm":"true","SendCalendarInvitationsOrCancellations":"SendToNone","MessageDisposition":"SendAndSaveCopy","SuppressReadReceipts":"false",
        "ComposeOperation":"newMail","OutboundCharset":"AutoDetect","PromoteInlineAttachments":"false","SendOnNotFoundError":"true"}}

        query['Body']['ItemChanges'][0]['Updates'][4]['Item']['ToRecipients'] = recipients

        self.__set_action_headers('UpdateItem', 'UpdateMessageForComposeSend', id)

        r = self.session.post(self.url + 'service.svc?action=UpdateItem&ID=-' + str(id) + '&AC=1', json=query, headers=self.mailHeaders)

        if r.status_code != 200:
            return False

        return True
