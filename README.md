# Reflect KZ automation

Автоматизация процесса отражения КЗ (СЗиП)

## Развертывание робота

1. Клонировать проект из репозитория: `git`
   (может потребоваться настройка [ssh])
2. Создать виртуальное окружение в корне проекта (откройте cmd или терминал в своей idle): `python -m venv venv`
3. Запустить виртуальное окружение: `venv\Scripts\activate.bat`
4. Установить внешние зависимости: `pip install -r requirements.txt`
5. Установить внутренние зависимости:
   
    `pip install --index-url http://--trusted-host  -r requirements-inner.txt`
    **ВНИМАНИЕ!** Для корректного запуска робота необходимо **обязательно** проделать действия из пунктов 4 и 5

6. Создать .env со следующими переменными:
```
# DB connection data
db_dsn=DRIVER={SQL Server};SERVER=;DATABASE=;UID=login;PWD=password

# SAP Fiori auth data
sap_fiori_login=login
sap_fiori_pass=password

# SAP Web Gui auth data
sap_gui_login=login
sap_gui_pass=password

# Mail auth data
mail_login=DOMAIN\first_name.last_name
mail_pass=password
```
7. В файле `config.py` заполнить:
   
    7.1 Адрес получателя писем об ошибках `USER_EMAIL = 'login@domain'` в строковом формате
    
    7.2 Адрес отправителя писем об ошибках `EMAIL_SENDER = 'login@domain'` в строковом формате

## Запуск робота

Робот запускается после активации виртуального окружения `venv\Scripts\activate.bat` командой:

```
python main.py
```
