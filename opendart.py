# Author: Yogyui
import os
import io
import re
import sys
import time
import shutil
import pickle
import pymysql
import zipfile
import datetime
import requests
import lxml.html
import subprocess
import pandas as pd
import logging.handlers
from enum import Enum, auto
from lxml import etree, html
from functools import partial
from collections import OrderedDict
from requests_html import AsyncHTMLSession
from abc import ABCMeta, abstractmethod
from typing import List, Union, Tuple, Iterable
from config import OpenDartConfiguration
from define import *
from Util import Callback


url_opendart = 'https://opendart.fss.or.kr/api/{}'


def convertTagToDict(tag: etree.Element) -> dict:
    conv = dict()
    for child in list(tag):
        conv[child.tag] = child.text
    return conv


class ApiResponseException(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message


class MySqlException(Exception):
    def __init__(self, code: int, message: str):
        self.code = code
        self.message = message


class LogType(Enum):
    Command = auto()
    Info = auto()
    API = auto()
    Error = auto()


class ReportCode(Enum):
    Buisness = '11011'
    HalfYear = '11012'
    FirstQuater = '11013'
    ThirdQueater = '11014'


class OpenDartCore:
    __metaclass__ = ABCMeta

    _df_corplist: pd.DataFrame = None
    _logger_console: logging.Logger
    _write_log_console_to_file: bool = False
    _empty_dataframe_with_columns: bool = True
    _rename_dataframe_column_names: bool = True
    _mysql_connection: Union[pymysql.connections.Connection, None] = None
    _asession_html: AsyncHTMLSession

    def __init__(self, api_key: str = None):
        curpath = os.path.dirname(os.path.abspath(__file__))

        self._path_data_dir: str = os.path.join(curpath, 'Data')
        if not os.path.isdir(self._path_data_dir):
            os.mkdir(self._path_data_dir)
        self._path_corp_df_pkl_file: str = os.path.join(self._path_data_dir, 'Corplist.pkl')

        self._path_log_dir: str = os.path.join(curpath, 'Log')
        if not os.path.isdir(self._path_log_dir):
            os.mkdir(self._path_log_dir)
        self._initLoggerConsole()

        self._callback_api_response_exception = Callback(int, str)
        self._callback_raw_html_download_done = Callback()
        self._callback_mysql_exception = Callback(int, str)
        self._callback_request_exception = Callback()

        self._config = OpenDartConfiguration()
        self._connectMySqlDatabase()
        self._initAsyncHtmlSession()

        if api_key is not None:
            self.setApiKey(api_key)
        self.loadCorporationDataFrame()

    def __del__(self):
        self.release()

    def release(self):
        self._closeAsyncHtmlSession()
        self._disconnectMySqlDatabase()

    def _initLoggerConsole(self):
        self._logger_console = logging.getLogger('opendart_console')
        filepath = os.path.join(self._path_log_dir, 'console.log')
        maxBytes = 100 * 1024 * 1024
        handler = logging.handlers.RotatingFileHandler(filepath, maxBytes=maxBytes, backupCount=10, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s]%(message)s')
        handler.setFormatter(formatter)
        self._logger_console.addHandler(handler)
        self._logger_console.setLevel(logging.DEBUG)

    def _log(self, message: str, logType: LogType = LogType.Info):
        now = datetime.datetime.now()
        strTimeStamp = now.strftime('[%Y-%m-%d %H:%M:%S.%f]')
        strLogType = '[ unknown]'
        strColorStart = ''
        strColorEnd = ''
        if logType == LogType.Command:
            strLogType = '[ command]'
        elif logType == LogType.Info:
            strLogType = '[    info]'
        elif logType == LogType.API:
            strLogType = '[     api]'
        elif logType == LogType.Error:
            strLogType = '[   error]'
            strColorStart = '\033[91m'
            strColorEnd = '\033[0m'
        print(strTimeStamp + strLogType + ' ' + strColorStart + message + strColorEnd)
        if self._write_log_console_to_file:
            self._logger_console.info(strLogType + ' ' + message)

    def log(self, *args, **kwargs):
        self._log(*args, **kwargs)

    def _requestWithParameters(self, url: str, params: dict) -> requests.Response:
        response = requests.get(url, params=params)
        message = f"<status:{response.status_code}> "
        message += f"<elapsed:{response.elapsed.microseconds/1000}ms> "
        message += f"<url:{response.request.url}> "
        self._log(message, LogType.API)
        return response

    def _requestAndGetContent(self, url: str, **kwargs) -> bytes:
        params = self._makeRequestParameter(**kwargs)
        resp = self._requestWithParameters(url, params)
        return resp.content

    def _requestAndGetJson(self, url: str, **kwargs) -> dict:
        params = self._makeRequestParameter(**kwargs)
        resp = self._requestWithParameters(url, params)
        return resp.json()

    def registerCallbackApiResponseException(self, func):
        self._callback_api_response_exception.connect(func)

    def registerCallbackDocumentRawHtmlDownloadDone(self, func):
        self._callback_raw_html_download_done.connect(func)

    def isEnableWriteLogConsoleToFile(self) -> bool:
        return self._write_log_console_to_file

    def setEnableWriteLogConsoleToFile(self, enable: bool):
        self._write_log_console_to_file = enable

    def isEnableEmptyDataframeWithColumns(self) -> bool:
        return self._empty_dataframe_with_columns

    def setEnableEmptyDataframeWithColumns(self, enable: bool):
        self._empty_dataframe_with_columns = enable

    def isEnableRenameDataframeColumnNames(self) -> bool:
        return self._rename_dataframe_column_names

    def setEnableRenameDataframeColumnNames(self, enable: bool):
        self._rename_dataframe_column_names = enable

    def setApiKey(self, key: str):
        self._config.api_key = key
        self._log(f"set api key: {self._config.api_key}", LogType.Command)
        self._config.saveToLocalFile()
        self.loadCorporationDataFrame()

    def getApiKey(self) -> str:
        return self._config.api_key

    def _makeRequestParameter(self, **kwargs) -> dict:
        params: dict = {'crtfc_key': self._config.api_key}
        params.update(kwargs)
        return params

    def _requestAndExtractZipFile(self, url: str, dest_dir: str = '', **kwargs) -> List[str]:
        content = self._requestAndGetContent(url, **kwargs)
        try:
            iostream = io.BytesIO(content)
            zf = zipfile.ZipFile(iostream)
            info = zf.infolist()
            filenames = [x.filename for x in info]
            self._log("filenames in zip file contents: {}".format(', '.join(filenames)), LogType.Info)
            path_dest = os.path.join(self._path_data_dir, dest_dir)
            zf.extractall(path_dest)
            zf.close()
            self._log(f"extracted {len(filenames)} file(s) to {path_dest}", LogType.Info)
            return filenames
        except zipfile.BadZipfile:
            self._parseResultFromResponse(content)

    def _parseResultFromResponse(self, content: bytes):
        node_result = etree.fromstring(content)
        node_status = node_result.find('status')
        node_message = node_result.find('message')
        status_code = int(node_status.text)
        message = node_message.text
        if status_code != 0:
            self._callback_api_response_exception.emit(status_code, message)
            raise ApiResponseException(status_code, message)

    def clearDocumentFilesFromDataPath(self):
        doc_extensions = ['.xml', '.html']
        files_in_datapath = os.listdir(self._path_data_dir)
        targets = list(filter(lambda x: os.path.splitext(x)[-1] in doc_extensions, files_in_datapath))
        if len(targets) > 0:
            target_paths = [os.path.join(self._path_data_dir, x) for x in targets]
            for filepath in target_paths:
                os.remove(filepath)
            self._log(f"removed {len(target_paths)} document files", LogType.Info)

    def _checkResponseStatus(self, json_obj: dict):
        status = json_obj.get('status')
        message = json_obj.get('message')
        if status != '000':
            status_code = int(status)
            self._callback_api_response_exception.emit(status_code, message)
            raise ApiResponseException(status_code, message)

    def _createEmptyDataFrame(self, column_names: Union[List[str], dict]) -> pd.DataFrame:
        df_result = pd.DataFrame()
        if self._empty_dataframe_with_columns:
            if isinstance(column_names, dict):
                if self._rename_dataframe_column_names:
                    column_names = list(column_names.values())
                else:
                    column_names = list(column_names.keys())
            for name in column_names:
                df_result[name] = None
        return df_result

    def _setReadyForCorporationDataFramePickleFile(self, reload: bool = False):
        if os.path.isfile(self._path_corp_df_pkl_file):
            if reload:
                os.remove(self._path_corp_df_pkl_file)
            else:
                moditime = time.ctime(os.path.getmtime(self._path_corp_df_pkl_file))
                modidate = datetime.datetime.strptime(moditime, "%a %b %d %H:%M:%S %Y")
                now = datetime.datetime.now()
                delta = now - modidate
                if delta.days > 0:
                    os.remove(self._path_corp_df_pkl_file)

    def _tryLoadingCorporationDataFrameFromPickleFile(self) -> bool:
        result = False
        if os.path.isfile(self._path_corp_df_pkl_file):
            try:
                with open(self._path_corp_df_pkl_file, 'rb') as fp:
                    self._df_corplist = pickle.load(fp)
                    result = True
            except Exception:
                pass
        return result

    def _makeCorporationDataFrameFromFile(self, removeFile: bool = True):
        try:
            path_file = os.path.join(self._path_data_dir, 'CORPCODE.xml')
            tree = etree.parse(path_file)
            root = tree.getroot()
            tags_list = root.findall('list')  # convert all <list> tag child to dict object
            tags_list_dict = [convertTagToDict(x) for x in tags_list]
            self._df_corplist = pd.DataFrame(tags_list_dict)
            if removeFile:
                os.remove(path_file)
        except FileNotFoundError:
            self._log(f"corporation code xml file is missing", LogType.Error)
            self._df_corplist = self._createEmptyDataFrame(ColumnNames.corp_code)

        if self._rename_dataframe_column_names:
            self._df_corplist.rename(columns=ColumnNames.corp_code, inplace=True)
        # change 'modify_date' type (str -> datetime)
        self._df_corplist['최종변경일자'] = pd.to_datetime(self._df_corplist['최종변경일자'], format='%Y%m%d')
        # drop test record (금감원테스트)
        colnames = self._df_corplist.columns
        row_unnecessary = self._df_corplist[self._df_corplist[colnames[0]] == '99999999']
        index = row_unnecessary.index
        self._df_corplist.drop(index, inplace=True)

    def _serializeCorporationDataFrame(self):
        with open(self._path_corp_df_pkl_file, 'wb') as fp:
            pickle.dump(self._df_corplist, fp)

    def _removeDocumentRawFileInLocal(self, document_no: str):
        path_file = os.path.join(self._path_data_dir, f'{document_no}.xml')
        if os.path.isfile(path_file):
            os.remove(path_file)

    def _isDocumentRawFileExistInLocal(self, document_no: str) -> bool:
        path_file = os.path.join(self._path_data_dir, f'{document_no}.xml')
        return os.path.isfile(path_file)

    def _solveDocumentRawFileEncodingIssue(self, document_no: str):
        path_file = os.path.join(self._path_data_dir, f'{document_no}.xml')
        if os.path.isfile(path_file):
            regexAnnotation = re.compile(r"<주[^>]*>")

            def replaceAnnotationBracket(source: str) -> str:
                search = regexAnnotation.search(source)
                result = source
                if search is not None:
                    span = search.span()
                    result = source[:span[0]] + '&lt;' + source[span[0] + 1:span[1] - 1] + '&gt;' + source[span[1]:]
                return result

            with open(path_file, 'r', encoding='euc-kr') as fp:
                doc_lines = fp.readlines()
                for replace_set in self._config.doc_str_replace_list:
                    src = replace_set[0]
                    dest = replace_set[1]
                    doc_lines = [x.replace(src, dest) for x in doc_lines]
                doc_lines = [replaceAnnotationBracket(x) for x in doc_lines]

            with open(path_file, 'w', encoding='utf-8') as fp:
                fp.writelines(doc_lines)

    def _logRequestResponse(self, req_type: str, response: requests.models.Response):
        message = f"{req_type} <status:{response.status_code}> "
        message += f"<elapsed:{response.elapsed.microseconds / 1000}ms> "
        message += f"<encoding:{response.html.encoding}> "
        message += f"<url:{response.url}> "
        # message += f"<headers:{response.headers}> "
        self._log(message, LogType.API)

    def _initAsyncHtmlSession(self):
        self._asession_html = AsyncHTMLSession()

    async def _asyncCloseSession(self):
        await self._asession_html.close()

    def _closeAsyncHtmlSession(self):
        self._asession_html.run(self._asyncCloseSession)

    async def _asyncGet(self, url: str, params: dict = None) -> requests.models.Response:
        try:
            response = await self._asession_html.get(url, params=params)
            self._logRequestResponse('get', response)
        except requests.exceptions.ConnectionError as e:
            self._log(f'request exception - {e}', LogType.Error)
            self._callback_request_exception.emit()
            response = None
        return response

    def _requestGet(self, url: str, params: dict = None) -> requests.models.Response:
        result = self._asession_html.run(lambda: self._asyncGet(url, params))
        response = result[0]
        return response

    async def _asyncGetRender(self, url: str,  params: dict = None, script: str = None) -> tuple:
        try:
            response = await self._asession_html.get(url, params=params)
            self._logRequestResponse('get', response)
            tm_start = time.perf_counter()
            result = await response.html.arender(script=script, reload=True, wait=0)
            elapsed = time.perf_counter() - tm_start
            self._log(f"render done (elapsed: {elapsed} sec)", LogType.Info)
        except requests.exceptions.ConnectionError as e:
            self._log(f'request exception - {e}', LogType.Error)
            self._callback_request_exception.emit()
            response, result = None, None
        return response, result

    def _requestGetRenderScript(self, url: str, params: dict = None, script: str = None) -> tuple:
        result = self._asession_html.run(lambda: self._asyncGetRender(url, params, script))
        response, obj = result[0]
        return response, obj

    async def _asyncPost(self, url: str, data: dict = None) -> requests.models.Response:
        try:
            response = await self._asession_html.post(url, data=data)
            self._logRequestResponse('post', response)
        except requests.exceptions.ConnectionError as e:
            self._log(f'request exception - {e}', LogType.Error)
            self._callback_request_exception.emit()
            response = None
        return response

    def _requestPost(self, url: str, data: List[dict]) -> List[requests.models.Response]:
        # TODO: use event loop
        result = self._asession_html.run(*[partial(self._asyncPost, url, x) for x in data])
        return result

    @staticmethod
    def _modifyTagAttributesOfDocumentResponse(response: requests.models.Response) -> lxml.html.HtmlElement:
        element = response.html.lxml
        tag_link = element.find('.//link')
        tag_link.attrib['href'] = "https://dart.fss.or.kr{}".format(tag_link.attrib['href'])
        tags_img = element.findall('.//img')
        for tag in tags_img:
            tag.attrib['src'] = "https://dart.fss.or.kr{}".format(tag.attrib['src'])
        return element

    def _saveElementToLocalHtmlFile(self, html_element: lxml.html.HtmlElement, document_no: str, encoding: str):
        str_enc = etree.tostring(html_element, encoding=encoding, method='html', pretty_print=True)
        str_dec = str_enc.decode(encoding)
        path_dest = os.path.join(self._path_data_dir, f'{document_no}.html')
        with open(path_dest, 'w', encoding=encoding) as fp:
            fp.write(str_dec)

    def _isDocumentHtmlFileExistInLocal(self, document_no: str) -> bool:
        path_file = os.path.join(self._path_data_dir, f'{document_no}.html')
        return os.path.isfile(path_file)

    def _removeDocumentHtmlFileInLocal(self, document_no: str):
        path_file = os.path.join(self._path_data_dir, f'{document_no}.html')
        if os.path.isfile(path_file):
            os.remove(path_file)

    def _makeDataFrameFromJsonList(self, json: dict, col_names: dict) -> pd.DataFrame:
        data_list = json.get('list')
        df = pd.DataFrame(data_list)
        if self._rename_dataframe_column_names:
            df.rename(columns=col_names, inplace=True)
        return df

    def _makeDataFrameFromJsonGroup(self, json: dict, title: str, col_names: dict) -> pd.DataFrame:
        group = list(filter(lambda x: x.get('title') == title, json.get('group')))[0]
        data_list = group.get('list')
        df = pd.DataFrame(data_list)
        if self._rename_dataframe_column_names:
            df.rename(columns=col_names, inplace=True)
        return df

    def _isFinancialStatementsDirExistInLocal(self, receiptNo: str, reportCode: Union[ReportCode, str]) -> bool:
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        path_dir = os.path.join(self._path_data_dir, f'fs_{receiptNo}_{rptcode}')
        return os.path.isdir(path_dir)

    def _removeFinancialStatementsDirInLocal(self, receiptNo: str, reportCode: Union[ReportCode, str]):
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        path_dir = os.path.join(self._path_data_dir, f'fs_{receiptNo}_{rptcode}')
        if os.path.isdir(path_dir):
            shutil.rmtree(path_dir)

    @staticmethod
    def _getParamWithBeginEndDate(
            corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> dict:
        params = {'corp_code': corpCode.strip()}
        if isinstance(dateBegin, datetime.date):
            params['bgn_de'] = dateBegin.strftime('%Y%m%d')
        else:
            params['bgn_de'] = dateBegin.strip()
        if isinstance(dateEnd, datetime.date):
            params['end_de'] = dateEnd.strftime('%Y%m%d')
        else:
            params['end_de'] = dateEnd.strip()
        return params

    def _makeHighlightsDataFrameCommon(
            self, corp_code: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date],
            api: str, col_names: dict
    ) -> pd.DataFrame:
        params = self._getParamWithBeginEndDate(corp_code, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format(api), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(col_names)
        df_result = self._makeDataFrameFromJsonList(json, col_names)
        return df_result

    def _makeBusinessReportDataFrameCommon(
            self, corp_code: str, year: int, rpt_code: str, api: str, col_names: dict
    ) -> pd.DataFrame:
        corp_code = corp_code.strip()
        rpt_code = rpt_code.strip()
        params = {'corp_code': corp_code, 'bsns_year': str(max(2015, year)), 'reprt_code': rpt_code}
        json = self._requestAndGetJson(url_opendart.format(api), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(col_names)
        df_result = self._makeDataFrameFromJsonList(json, col_names)
        return df_result

    def _makeFinancialDataFrameCommon(
            self, corp_code: Union[str, List[str]], year: int, rpt_code: str, api: str, col_names: dict, **kwargs
    ) -> pd.DataFrame:
        if isinstance(corp_code, list):
            corp_code = ','.join([x.strip() for x in corp_code])
        else:
            corp_code = corp_code.strip()
        rpt_code = rpt_code.strip()
        params = {'corp_code': corp_code, 'bsns_year': str(max(2015, year)), 'reprt_code': rpt_code}
        for key, value in kwargs.items():
            params[key] = value
        json = self._requestAndGetJson(url_opendart.format(api), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(col_names)
        df_result = self._makeDataFrameFromJsonList(json, col_names)
        return df_result

    def _connectMySqlDatabase(self):
        try:
            host = self._config.mysql_params.get('host')
            port = self._config.mysql_params.get('port')
            user = self._config.mysql_params.get('user')
            passwd = self._config.mysql_params.get('password')
            db = self._config.mysql_params.get('databse')
            if len(host) > 0:
                self._mysql_connection = pymysql.connect(host=host, port=port, user=user, passwd=passwd, db=db)
                self._log('connected to mysql database', LogType.Info)
            else:
                self._log('check mysql database parameters', LogType.Info)
        except pymysql.err.OperationalError as e:
            self._callback_mysql_exception.emit(e.args[0], e.args[1])
            self._log(f"mysql exception({e.args[0]}) - {e.args[1]}", LogType.Error)
            self._mysql_connection = None

    def _disconnectMySqlDatabase(self):
        if self._mysql_connection is not None:
            self._mysql_connection.close()

    def _queryMySql(self, sql: str) -> Tuple:
        cursor = self._mysql_connection.cursor()
        result = cursor.execute(sql)
        self._log(f"mysql query ({result}) ({sql})", LogType.Info)
        fetch = cursor.fetchall()
        return fetch

    def _queryManyMySql(self, sql: str, data: Iterable):
        cursor = self._mysql_connection.cursor()
        result = cursor.executemany(sql, data)
        self._log(f"mysql query many ({result}) ({sql})", LogType.Info)
        fetch = cursor.fetchall()
        return fetch

    def _isTableExistInDatabase(self, table_name: str) -> bool:
        result = self._queryMySql("SHOW TABLES;")
        tables = [x[0] for x in result]
        return table_name.lower() in tables

    def _createCorporationTableInMySqlDatabase(self):
        if self._mysql_connection is None:
            return
        table_name = 'CORPORATION'
        self._log('try to create corporation table in mysql database', LogType.Command)
        if self._isTableExistInDatabase(table_name):
            self._log(f"mysql - table '{table_name}' is already in database", LogType.Info)
        else:
            sql = f"CREATE TABLE `{table_name}` ("
            sql += "`고유번호` CHAR(8), "
            sql += "`기업명` VARCHAR(32) NOT NULL, "
            sql += "`종목코드` CHAR(6), "
            sql += "`최종변경일자` DATE NOT NULL, "
            sql += "PRIMARY KEY(`고유번호`)"
            sql += ");"
            self._queryMySql(sql)
            self._mysql_connection.commit()

    def _selectRecordsFromCorporationTableInMySql(self) -> pd.DataFrame:
        self._log('try to select all records from corporation table in mysql database', LogType.Command)
        records = self._queryMySql("SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME='CORPORATION';")
        colnames = [x[0] for x in records]
        records = self._queryMySql("SELECT * FROM CORPORATION;")
        df = pd.DataFrame(records)
        if df.empty:
            df[colnames] = None
        else:
            df.columns = colnames
        return df

    def _updateRecordsOfCorporationTableInMySql(self):
        if self._mysql_connection is None:
            return

        self._log('try to update corporation table in mysql database', LogType.Command)
        table_name = 'CORPORATION'
        if not self._isTableExistInDatabase(table_name):
            self._createCorporationTableInMySqlDatabase()
        df_db = self._selectRecordsFromCorporationTableInMySql()
        data_insert = []
        data_update = []
        colnames = self._df_corplist.columns

        for i in range(len(self._df_corplist)):
            record = self._df_corplist.iloc[i]
            corp_code = record[colnames[0]]
            name = record[colnames[1]]
            stock_code = record[colnames[2]].strip()
            date = record[colnames[3]].strftime('%Y-%m-%d')
            if corp_code in df_db['고유번호'].values:
                record_db = df_db[df_db['고유번호'] == corp_code]
                name_db = record_db['기업명'].values[0]
                stock_db = record_db['종목코드'].values[0]
                date_db = record_db['최종변경일자'].values[0].strftime('%Y-%m-%d')
                if name_db != name or stock_db != stock_code or date_db != date:
                    if len(stock_code) == 0:
                        stock_code = None
                    data_update.append((name, stock_code, date, corp_code))
            else:
                if len(stock_code) == 0:
                    stock_code = None
                data_insert.append((corp_code, name, stock_code, date))
        self._log(f'insert/update dataset (insert: {len(data_insert)}, update: {len(data_update)})', LogType.Info)

        if len(data_insert) > 0:
            sql = f"INSERT INTO `{table_name}` (`고유번호`, `기업명`, `종목코드`, `최종변경일자`) "
            sql += f"VALUES (%s, %s, %s, %s);"
            self._queryManyMySql(sql, data_insert)
        if len(data_update) > 0:
            sql = f"UPDATE `{table_name}` SET `기업명`=%s, `종목코드`=%s, `최종변경일자`=%s WHERE `고유번호`=%s;"
            self._queryManyMySql(sql, data_update)

        self._mysql_connection.commit()

    @abstractmethod
    def loadCorporationDataFrame(self, reload: bool = False) -> pd.DataFrame:
        self._df_corplist = pd.DataFrame()
        if self._rename_dataframe_column_names:
            column_names = list(ColumnNames.corp_code.values())
        else:
            column_names = list(ColumnNames.corp_code.keys())
        for name in column_names:
            self._df_corplist[name] = None
        return self._df_corplist

    @staticmethod
    def _makeDataframeFromDailyDocumentElementTree(tree: etree.ElementTree) -> pd.DataFrame:
        tbList = tree.find_class('tbList')[0]
        tbody = tbList.find('tbody')
        tr_list = tbody.findall('tr')
        element_list = []
        corp_code_regex = re.compile(r"[0-9]{8}")

        for tr in tr_list:
            td_list = tr.findall('td')
            strtime = td_list[0].text.strip()

            name_span = td_list[1].find('span')  # <span class="innerWrap">
            name_a = name_span.find('a')
            name = name_a.text
            name = name.replace('\t', '')
            name = name.replace('\n', '')
            name = name.strip()

            name_attrib_href = name_a.attrib.get('href')
            corp_code_search = corp_code_regex.search(name_attrib_href)
            corp_code = ''
            if corp_code_search is not None:
                span = corp_code_search.span()
                corp_code = name_attrib_href[span[0]:span[1]]

            class_span = name_span.find('span')
            corp_class = class_span.attrib.get('title')

            rpt_a = td_list[2].find('a')
            rpt_attrib_id = rpt_a.attrib.get('id')
            rpt = rpt_a.text
            if rpt is None:
                rpt_span = rpt_a.find('span')
                rpt = rpt_span.text + rpt_span.tail
            rpt = rpt.replace('\t', '')
            rpt = rpt.replace('\n', '')
            rpt = rpt.replace('  ', ' ')
            rpt = rpt.strip()

            rpt_no = rpt_attrib_id.split('_')[-1]

            flr_nm = td_list[3].text
            rcept_dt = td_list[4].text
            tag_rm = td_list[5]
            rm = ' '.join([x.text for x in tag_rm.findall('span')])

            element = OrderedDict()
            element['시간'] = strtime
            element['고유번호'] = corp_code
            element['분류'] = corp_class
            element['공시대상회사'] = name
            element['보고서명'] = rpt
            element['보고서번호'] = rpt_no
            element['제출인'] = flr_nm
            element['접수일자'] = rcept_dt
            element['비고'] = rm
            element_list.append(element)
        df = pd.DataFrame(element_list)
        return df


class OpenDart(OpenDartCore):
    """ 유틸리티"""

    def getDailyUploadedDocuments(self, date: Union[datetime.date, str], corpClass: str = None) -> pd.DataFrame:
        """
        특정 날짜에 공시된 모든 문서 리스트를 데이터프레임으로 반환

        :param date: 검색대상일자 (str일 경우 format = YYYY.mm.dd)
        :param corpClass: 법인구분 (Y(유가), K(코스닥), N(코넥스), E(기타)), None일 경우 모두 검색
        :return: pandas DataFrame (columns: 시간, 고유번호, 공시대상회사, 보고서명, 보고서번호, 제출인, 접수일자)
        """
        if corpClass in ['Y', 'K', 'N']:
            url = f'http://dart.fss.or.kr/dsac001/main{corpClass}.do'
        elif corpClass == 'E':
            url = f'http://dart.fss.or.kr/dsac001/mainG.do'
        else:
            url = 'http://dart.fss.or.kr/dsac001/mainAll.do'
        if isinstance(date, datetime.date):
            search_date = date.strftime('%Y.%m.%d')
        else:
            search_date = date
        params = {'selectDate': search_date}
        response = self._requestGet(url, params)
        if response is None:
            return pd.DataFrame()

        tree = response.html.lxml
        pageSkip = tree.find_class('pageSkip')[0]
        pageSkip_ul = pageSkip.find('ul')
        li_list = pageSkip_ul.findall('li')
        page_count = len(li_list)
        df_result = self._makeDataframeFromDailyDocumentElementTree(tree)

        if page_count > 1:
            url = 'http://dart.fss.or.kr/dsac001/search.ax'
            data_list = [{
                'currentPage': x + 1,
                'selectDate': date,
                'mdayCnt': 0
            } for x in range(1, page_count)]
            responses = self._requestPost(url, data_list)
            df_list = [self._makeDataframeFromDailyDocumentElementTree(x.html.lxml) for x in responses]
            df_result = [df_result]
            df_result.extend(df_list)
            df_result = pd.concat(df_result, axis=0, ignore_index=True)

        df_result.sort_values(by='시간', inplace=True)
        df_result.reset_index(drop=True, inplace=True)

        return df_result

    """ 공시정보 API """

    def searchDocument(
            self, corpCode: str = None, dateEnd: Union[str, datetime.date] = datetime.datetime.now().date(),
            dateBegin: Union[str, datetime.date] = None, finalReport: bool = True, pageNumber: int = 1,
            pageCount: int = 100, pbType: str = None, pbTypeDetail: str = None, corpClass: str = None,
            recursive: bool = False
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001
        [공시정보::1.공시검색]
        공시 유형별, 회사별, 날짜별 등 여러가지 조건으로 공시보고서 검색기능을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateEnd: 검색종료 접수일자(YYYYMMDD), 기본값 = 호출당일
        :param dateBegin: 검색시작 접수일자(YYYYMMDD)
        :param finalReport: 최종보고서만 검색여부, 기본값 = True(정정이 있는 경우 최종정정만 검색)
        :param pageNumber: 페이지 번호, 기본값 = 1
        :param pageCount: 페이지당 건수, 기본값 = 100 (범위 = 1 ~ 100)
        :param pbType: 공시유형 (define -> dict_pblntf_ty 참고)
        :param pbTypeDetail: 공시유형 (define -> dict_pblntf_detail_ty 참고)
        :param corpClass: 법인구분 (Y(유가), K(코스닥), N(코넥스), E(기타))
        :param recursive: 메서드 내부에서의 재귀적 호출인지 여부 (여러 페이지의 레코드를 모두 병합)
        :return: pandas DataFrame
        """
        self._log("search document", LogType.Command)
        params = dict()
        if isinstance(dateEnd, datetime.date):
            params['end_de'] = dateEnd.strftime('%Y%m%d')
        else:
            params['end_de'] = dateEnd

        if corpCode is not None:
            params['corp_code'] = corpCode
        if dateBegin is not None:
            if isinstance(dateBegin, datetime.date):
                params['bgn_de'] = dateBegin.strftime('%Y%m%d')
            else:
                params['bgn_de'] = dateBegin
        else:
            if isinstance(dateEnd, datetime.date):
                params['bgn_de'] = (dateEnd - datetime.timedelta(days=30)).strftime('%Y%m%d')
            else:
                dateEnd = datetime.datetime.strptime(dateEnd, '%Y%m%d')
                params['bgn_de'] = (dateEnd - datetime.timedelta(days=30)).strftime('%Y%m%d')
        params['last_reprt_at'] = 'Y' if finalReport else 'N'
        params['page_no'] = max(1, pageNumber)
        params['page_count'] = max(1, min(100, pageCount))
        if pbType is not None:
            params['pblntf_ty'] = pbType
        if pbTypeDetail is not None:
            params['pblntf_detail_ty'] = pbTypeDetail
        if corpClass is not None:
            params['corp_cls'] = corpClass

        json = self._requestAndGetJson(url_opendart.format("list.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.search_document)

        page_no = json.get('page_no')
        total_page = json.get('total_page')
        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        if self._rename_dataframe_column_names:
            df_result.rename(columns=ColumnNames.search_document, inplace=True)

        if not recursive:  # loop query more than 1 page - recursive call
            for page in range(page_no + 1, total_page + 1):
                df_next = self.searchDocument(corpCode, dateEnd, dateBegin, finalReport,
                                              page, pageCount, pbType, pbTypeDetail, corpClass,
                                              recursive=True)
                df_result = pd.concat([df_result, df_next], axis=0, ignore_index=True)

        return df_result

    def getCompanyInformation(
            self, corpCode: str
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002
        [공시정보::2.기업개황]
        DART에 등록되어있는 기업의 개황정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :return: pandas DataFrame
        """
        corpCode = corpCode.strip()
        self._log(f"get company information (corp code: {corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        json = self._requestAndGetJson(url_opendart.format("company.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.company)

        df_result = pd.DataFrame([json])
        df_result.pop("status")
        df_result.pop("message")

        if self._rename_dataframe_column_names:
            df_result.rename(columns=ColumnNames.company, inplace=True)
        return df_result

    def downloadDocumentRawFile(
            self, document_no: str, reload: bool = False
    ):
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003
        [공시정보::3.공시서류원본파일]
        공시보고서 원본파일을 제공합니다.

        :param document_no: 접수번호
        :param reload: 파일이 존재할 경우 삭제하고 다시 다운로드받을 지 여부
        """
        document_no = document_no.strip()
        params = {'rcept_no': document_no}
        if reload:
            self._removeDocumentRawFileInLocal(document_no)
        if not self._isDocumentRawFileExistInLocal(document_no):
            self._log(f"download document raw file (doc no: {document_no})", LogType.Command)
            try:
                self._requestAndExtractZipFile(url_opendart.format("document.xml"), **params)
            except ApiResponseException as e:
                self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            self._solveDocumentRawFileEncodingIssue(document_no)

    def loadCorporationDataFrame(
            self, reload: bool = False
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003
        [공시정보::4.고유번호]
        DART에 등록되어있는 공시대상회사의 고유번호, 회사명, 종목코드, 최근변경일자를 파일로 제공합니다.

        :param reload: 1일단위 최신 여부와 관계없이 강제로 다시 불러오기 플래그
        :return: pandas DataFrame
        """
        if self._df_corplist is None:
            tm_start = time.perf_counter()
            self._log("load corporation list as dataframe", LogType.Command)
            self._setReadyForCorporationDataFramePickleFile(reload)
            if not self._tryLoadingCorporationDataFrameFromPickleFile():
                try:
                    self._requestAndExtractZipFile(url_opendart.format("corpCode.xml"))
                except ApiResponseException as e:
                    self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
                    self._df_corplist = self._createEmptyDataFrame(ColumnNames.corp_code)
                else:
                    self._makeCorporationDataFrameFromFile()
                self._serializeCorporationDataFrame()
            elapsed = time.perf_counter() - tm_start
            self._log(f'finished loading corporation list (elapsed: {elapsed} sec)', LogType.Info)
        return self._df_corplist

    def searchCorporationCodeWithName(
            self, name: str, match_exact: bool = False
    ) -> pd.DataFrame:
        """
        DART에 등록된 기업의 고유번호(corp_code)를 기업명으로 검색

        :param name: 검색할 기업명
        :param match_exact: True = 기업명 정확히 일치, False = 검색할 기업명이 포함되는 모든 레코드 반환
        :return: pandas DataFrame
        """
        self.loadCorporationDataFrame()
        if match_exact:
            df_filtered = self._df_corplist[self._df_corplist['정식명칭'] == name]
        else:
            df_filtered = self._df_corplist[self._df_corplist['정식명칭'].str.contains(name)]
        return df_filtered

    def readDocumentRawXmlFileAsString(
            self, document_no: str, reload: bool = False
    ) -> str:
        self.downloadDocumentRawFile(document_no, reload)
        path_file = os.path.join(self._path_data_dir, f'{document_no}.xml')
        raw_string = ''
        if os.path.isfile(path_file):
            with open(path_file, 'r', encoding='utf-8') as fp:
                raw_string = fp.read()
        return raw_string

    def downloadDocumentAsHtmlFile(
            self, document_no: str, reload: bool = False, openFile: bool = False
    ) -> str:
        if reload:
            self._removeDocumentHtmlFileInLocal(document_no)
        if not self._isDocumentHtmlFileExistInLocal(document_no):
            regex = re.compile(r"^[0-9]{14}$")
            if regex.search(document_no) is not None:
                self._log(f"download document as html file (doc no: {document_no})", LogType.Command)
                url_main = "https://dart.fss.or.kr/dsaf001/main.do"
                url_viewer = "https://dart.fss.or.kr/report/viewer.do"
                params = {"rcpNo": document_no}
                script = "currentDocValues;"  # returns 'rcpNo', 'dcmNo', 'eleId', 'offset', 'length', 'dtd'
                try:
                    _, obj = self._requestGetRenderScript(url_main, params, script)
                    self._log(f"get rendered object - {obj}", LogType.Info)
                    obj['offset'] = 0
                    obj['length'] = 0
                    response = self._requestGet(url_viewer, obj)
                    encoding = response.html.encoding
                    html_element = self._modifyTagAttributesOfDocumentResponse(response)
                    self._saveElementToLocalHtmlFile(html_element, document_no, encoding)
                except Exception as e:
                    self._log(str(e), LogType.Error)
                    return ''
            else:
                self._log(f'document number ({document_no}) is not well-formed', LogType.Error)
                return ''

        self._callback_raw_html_download_done.emit()

        path_dest = os.path.join(self._path_data_dir, f'{document_no}.html')
        if openFile and os.path.isfile(path_dest):
            if sys.platform == 'win32':
                os.startfile(path_dest)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, path_dest])

        return path_dest

    def loadDocumentHtmlFileAsElementTree(
            self, document_no: str, reload: bool = False
    ) -> etree.ElementTree:
        path_file = self.downloadDocumentAsHtmlFile(document_no, reload)
        if os.path.isfile(path_file):
            tree = html.parse(path_file)
        else:
            root = etree.Element('html')
            tree = etree.ElementTree(root)
        return tree

    def readDocumentHtmlFileAsText(
            self, document_no: str, reload: bool = False
    ) -> str:
        tree = self.loadDocumentHtmlFileAsElementTree(document_no, reload)
        encoding = tree.docinfo.encoding
        raw = html.tostring(tree, encoding=encoding)
        text = raw.decode(encoding=encoding)
        return text

    """ 사업보고서 주요정보 API """

    def getContingentConvertibleBondOutstandingBalanceInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020008
        [사업보고서 주요정보::1.조건부 자본증권 미상환 잔액]
        정기보고서(사업, 분기, 반기보고서) 내에 조건부 자본증권 미상환 잔액을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get contingent convertible bond outstanding balance info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "cndlCaplScritsNrdmpBlce.json", ColumnNames.outstanding_balance)
        return df_result

    def getUnregisteredOfficerRemunerationInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020013
        [사업보고서 주요정보::2.미등기임원 보수현황]
        정기보고서(사업, 분기, 반기보고서) 내에 미등기임원 보수현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get unregistered officer remuneration info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "unrstExctvMendngSttus.json", ColumnNames.remuneration)
        return df_result

    def getDebentureOutstandingBalanceInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020006
        [사업보고서 주요정보::3.회사채 미상환 잔액]
        정기보고서(사업, 분기, 반기보고서) 내에 회사채 미상환 잔액을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get debenture outstanding balance info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "cprndNrdmpBlce.json", ColumnNames.outstanding_balance)
        return df_result

    def getShortTermBondOutstandingBalanceInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020005
        [사업보고서 주요정보::4.단기사채 미상환 잔액]
        정기보고서(사업, 분기, 반기보고서) 내에 단기사채 미상환 잔액을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get short-term bond outstanding balance info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "srtpdPsndbtNrdmpBlce.json", ColumnNames.outstanding_balance)
        return df_result

    def getPaperSecuritiesOutstandingBalanceInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020004
        [사업보고서 주요정보::5.기업어음증권 미상환 잔액]
        정기보고서(사업, 분기, 반기보고서) 내에 기업어음증권 미상환 잔액을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get paper securities outstanding balance info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "entrprsBilScritsNrdmpBlce.json", ColumnNames.outstanding_balance)
        return df_result

    def getDebtSecuritiesPublishInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020003
        [사업보고서 주요정보::6.채무증권 발행실적]
        정기보고서(사업, 분기, 반기보고서) 내에 채무증권 발행실적을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get debt securities publish info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "detScritsIsuAcmslt.json", ColumnNames.debt_securities)
        return df_result

    def getPrivateCapitalUsageDetailInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020017
        [사업보고서 주요정보::7.사모자금의 사용내역]
        정기보고서(사업, 분기, 반기보고서) 내에 사모자금의 사용내역을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get private capital usage detail info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "prvsrpCptalUseDtls.json", ColumnNames.equity_usage_detail)
        return df_result

    def getPublicCapitalUsageDetailInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020016
        [사업보고서 주요정보::8.공모자금의 사용내역]
        정기보고서(사업, 분기, 반기보고서) 내에 공모자금의 사용내역을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get public equity usage detail info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "pssrpCptalUseDtls.json", ColumnNames.equity_usage_detail)
        return df_result

    def getEntireOfficerRemunerationByApprovalInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020014
        [사업보고서 주요정보::9.이사·감사 전체의 보수현황(주주총회 승인금액)]
        정기보고서(사업, 분기, 반기보고서) 내에 이사·감사 전체의 보수현황(주주총회 승인금액)을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get entire officer remuneration by approval info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "drctrAdtAllMendngSttusGmtsckConfmAmount.json", ColumnNames.remuneration)
        return df_result

    def getEntireOfficerRemunerationByPaymentsInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020015
        [사업보고서 주요정보::10.이사·감사 전체의 보수현황(보수지급금액 - 유형별)]
        정기보고서(사업, 분기, 반기보고서) 내에 이사·감사 전체의 보수현황(보수지급금액 - 유형별)을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get entire officer remuneration by payments info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "drctrAdtAllMendngSttusMendngPymntamtTyCl.json", ColumnNames.remuneration)
        return df_result

    def getStockTotalQuantityInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020002
        [사업보고서 주요정보::11.주식의 총수 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 주식의총수현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get stock total quantity info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "stockTotqySttus.json", ColumnNames.stock_quantity)
        return df_result

    def getAccountingAuditorAndOpinionInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020009
        [사업보고서 주요정보::12.회계감사인의 명칭 및 감사의견]
        정기보고서(사업, 분기, 반기보고서) 내에 회계감사인의 명칭 및 감사의견을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get accounting auditor and opinion info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "accnutAdtorNmNdAdtOpinion.json", ColumnNames.audit_opinion)
        return df_result

    def getAuditServiceContractStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020010
        [사업보고서 주요정보::13.감사용역체결현황]
        정기보고서(사업, 분기, 반기보고서) 내에 감사용역체결현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get audit service contract status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "adtServcCnclsSttus.json", ColumnNames.audit_service_contract)
        return df_result

    def getNonAuditServiceContractStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020011
        [사업보고서 주요정보::14.회계감사인과의 비감사용역 계약체결 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 회계감사인과의 비감사용역 계약체결 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get non-audit service contract status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "accnutAdtorNonAdtServcCnclsSttus.json", ColumnNames.non_audit_service_contract)
        return df_result

    def getOutsideDirectorAndChangeStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020012
        [사업보고서 주요정보::15.사외이사 및 그 변동현황]
        정기보고서(사업, 분기, 반기보고서) 내에 사외이사 및 그 변동현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get outside director and change status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "outcmpnyDrctrNdChangeSttus.json", ColumnNames.outside_director)
        return df_result

    def getHybridSecuritiesOutstandingBalanceInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2020007
        [사업보고서 주요정보::16.신종자본증권 미상환 잔액]
        정기보고서(사업, 분기, 반기보고서) 내에 신종자본증권 미상환 잔액을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get hybrid securities outstanding balance info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "newCaplScritsNrdmpBlce.json", ColumnNames.outstanding_balance)
        return df_result

    def getCapitalIncreaseDecreaseStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019004
        [사업보고서 주요정보::17.증자(감자) 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 증자(감자) 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get capital increase(decrease) status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "irdsSttus.json", ColumnNames.capital_inc_dec)
        return df_result

    def getDividendDetailInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019005
        [사업보고서 주요정보::18.배당에 관한 사항]
        정기보고서(사업, 분기, 반기보고서) 내에 배당에 관한 사항을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get dividend detail info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "alotMatter.json", ColumnNames.dividend_detail)
        return df_result

    def getTreasuryStockAcquisitionDisposalInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019006
        [사업보고서 주요정보::19.자기주식 취득 및 처분 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 자기주식 취득 및 처분 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get treasury stock acquisition(disposal) info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "tesstkAcqsDspsSttus.json", ColumnNames.treasury_stock)
        return df_result

    def getMajorityShareholderStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019007
        [사업보고서 주요정보::20.최대주주 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 최대주주 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get majority shareholder status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "hyslrSttus.json", ColumnNames.majority_shareholder)
        return df_result

    def getMajorityShareholderChangeStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019008
        [사업보고서 주요정보::21.최대주주 변동현황]
        정기보고서(사업, 분기, 반기보고서) 내에 최대주주 변동현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get majority shareholder change status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "hyslrChgSttus.json", ColumnNames.majority_shareholder_change)
        return df_result

    def getMinorityShareholderStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019009
        [사업보고서 주요정보::22.소액주주 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 소액주주 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get minority shareholder status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "mrhlSttus.json", ColumnNames.minority_shareholder)
        return df_result

    def getExecutivesStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019010
        [사업보고서 주요정보::23.임원 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 임원 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get executives status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "exctvSttus.json", ColumnNames.executives_status)
        return df_result

    def getEmployeeStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019011
        [사업보고서 주요정보::24.직원 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 직원 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get employee status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "empSttus.json", ColumnNames.employee_status)
        return df_result

    def getIndivisualOfficerRemunerationStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019012
        [사업보고서 주요정보::25.이사·감사의 개인별 보수 현황]
        정기보고서(사업, 분기, 반기보고서) 내에 이사·감사의 개인별 보수 현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get indivisual officer remuneration status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "hmvAuditIndvdlBySttus.json", ColumnNames.indivisual_officer_remuneration)
        return df_result

    def getEntireOfficerRemunerationStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019013
        [사업보고서 주요정보::26.이사·감사 전체의 보수현황]
        정기보고서(사업, 분기, 반기보고서) 내에 이사·감사 전체의 보수현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get entire officer remuneration status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "hmvAuditAllSttus.json", ColumnNames.entire_officer_remuneration)
        return df_result

    def getHighestIndivisualRemunerationInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019014
        [사업보고서 주요정보::27.개인별 보수지급 금액(5억이상 상위5인)]
        정기보고서(사업, 분기, 반기보고서) 내에 개인별 보수지급 금액(5억이상 상위5인)을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get highest indivisual remuneration info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "indvdlByPay.json", ColumnNames.indivisual_officer_remuneration)
        return df_result

    def getOtherCorporationInvestmentStatusInfo(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS002&apiId=2019015
        [사업보고서 주요정보::28.타법인 출자현황]
        정기보고서(사업, 분기, 반기보고서) 내에 타법인 출자현황을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get other corporation investment status info " + info, LogType.Command)
        df_result = self._makeBusinessReportDataFrameCommon(
            corpCode, year, rptcode, "otrCprInvstmntSttus.json", ColumnNames.other_corp_investment)
        return df_result

    """ 상장기업 재무정보 API """

    def getSingleFinancialInformation(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019016
        [상장기업 재무정보::1.단일회사 주요계정]
        상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 주요계정과목(재무상태표, 손익계산서)을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        corpCode = corpCode.strip()
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode.strip()
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get single financial information " + info, LogType.Command)
        df_result = self._makeFinancialDataFrameCommon(
            corpCode, year, rptcode, "fnlttSinglAcnt.json", ColumnNames.financial)
        return df_result

    def getMultiFinancialInformation(
            self, corpCode: List[str], year: int, reportCode: Union[ReportCode, str]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019017
        [상장기업 재무정보::2.다중회사 주요계정]
        상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 주요계정과목(재무상태표, 손익계산서)을 제공합니다.
        (상장법인 복수조회 가능)

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        corpCode = [x.strip() for x in corpCode]
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode.strip()
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get multiple financial information " + info, LogType.Command)
        df_result = self._makeFinancialDataFrameCommon(
            corpCode, year, rptcode, "fnlttMultiAcnt.json", ColumnNames.financial)
        return df_result

    def downloadFinancialStatementsRawFile(
            self, receiptNo: str, reportCode: Union[ReportCode, str], reload: bool = False,
            openFolder: bool = False
    ):
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019019
        [상장기업 재무정보::3.재무제표 원본파일(XBRL)]
        상장법인이 제출한 정기보고서 내에 XBRL재무제표의 원본파일(XBRL)을 제공합니다.

        :param receiptNo: 접수번호
        :param reportCode: 보고서 코드
        :param reload: 디렉터리가 존재할 경우 삭제하고 다시 다운로드받을 지 여부
        :param openFolder: 탐색기에서 다운로드받은 폴더를 열지 여부
        """
        receiptNo = receiptNo.strip()
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode.strip()
        dest_dir = f'fs_{receiptNo}_{rptcode}'

        if reload:
            self._removeFinancialStatementsDirInLocal(receiptNo, rptcode)
        if not self._isFinancialStatementsDirExistInLocal(receiptNo, rptcode):
            info = f"(receipt no: {receiptNo}, report code: {rptcode})"
            self._log("download financial statements raw file " + info, LogType.Command)
            params = {'rcept_no': receiptNo, 'reprt_code': rptcode}
            try:
                self._requestAndExtractZipFile(url_opendart.format("fnlttXbrl.xml"), dest_dir, **params)
            except ApiResponseException as e:
                self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)

        path_dest = os.path.join(self._path_data_dir, dest_dir)
        if openFolder and os.path.isdir(path_dest):
            if sys.platform == 'win32':
                os.startfile(path_dest)
            else:
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.call([opener, path_dest])

    def getEntireFinancialStatements(
            self, corpCode: str, year: int, reportCode: Union[ReportCode, str], financialDivision: str):
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020
        [상장기업 재무정보::4.단일회사 전체 재무제표]
        상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 모든계정과목을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :param financialDivision: 개별/연결 구분 (CFS: 연결재무제표, OFS: 재무제표)
        :return: pandas DataFrame
        """
        corpCode = corpCode.strip()
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode.strip()
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode}, fin-division: {financialDivision})"
        self._log("get entire financial information " + info, LogType.Command)
        df_result = self._makeFinancialDataFrameCommon(
            corpCode, year, rptcode, "fnlttSinglAcntAll.json", ColumnNames.entire_financial_statements,
            fs_div=financialDivision)
        return df_result

    def getXbrlTaxonomyFormat(self, div: str):
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2020001
        [상장기업 재무정보::5.XBRL택사노미재무제표양식]
        금융감독원 회계포탈에서 제공하는 IFRS 기반 XBRL 재무제표 공시용 표준계정과목체계(계정과목)을 제공합니다.

        :param div: 재무제표구분 - URL 재무제표구분 참조
        :return: pandas DataFrame
        """
        info = f"(div: {div})"
        self._log("get xbrl taxonomy format " + info, LogType.Command)
        params = {'sj_div': div.strip()}
        json = self._requestAndGetJson(url_opendart.format("xbrlTaxonomy.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.xbrl_taxonomy)
        df_result = self._makeDataFrameFromJsonList(json, ColumnNames.xbrl_taxonomy)
        return df_result

    """ 지분공시 종합정보 API """

    def getMajorStockInformation(
            self, corpCode: str
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019021
        [지분공시 종합정보::1.대량보유 상황보고]
        주식등의 대량보유상황보고서 내에 대량보유 상황보고 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :return: pandas DataFrame
        """
        corpCode = corpCode.strip()
        self._log(f"get major stock information (corp code: {corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        json = self._requestAndGetJson(url_opendart.format("majorstock.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.major_stock)

        df_result = self._makeDataFrameFromJsonList(json, ColumnNames.major_stock)
        return df_result

    def getExecutiveStockInformation(
            self, corpCode: str
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS004
        [지분공시 종합정보::2.임원ㆍ주요주주 소유보고]
        임원ㆍ주요주주특정증권등 소유상황보고서 내에 임원ㆍ주요주주 소유보고 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :return: pandas DataFrame
        """
        corpCode = corpCode.strip()
        self._log(f"get executive stock information (corp code: {corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        json = self._requestAndGetJson(url_opendart.format("elestock.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.executive_stock)

        df_result = self._makeDataFrameFromJsonList(json, ColumnNames.executive_stock)
        return df_result

    """ 주요사항보고서 주요정보 API """

    def getBankruptcyOccurrenceInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020019
        [주요사항보고서 주요정보::1.부도발생]
        주요사항보고서(부도발생) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get bankruptcy occurrence info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "dfOcr.json", ColumnNames.bankruptcy)
        return df_result

    def getBusinessSuspensionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020020
        [주요사항보고서 주요정보::2.영업정지]
        주요사항보고서(영업정지) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get business suspension info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "bsnSp.json", ColumnNames.suspension)
        return df_result

    def getRehabilitationProcedureInitiateInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020021
        [주요사항보고서 주요정보::3.회생절차 개시신청]
        주요사항보고서(회생절차 개시신청) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get rehabilitation procedure initiate info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "ctrcvsBgrq.json", ColumnNames.rehabilitation)
        return df_result

    def getDissolutionReasonOccurrenceInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020022
        [주요사항보고서 주요정보::4.해산사유 발생]
        주요사항보고서(해산사유 발생) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get dissolution reason occurrence info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "dsRsOcr.json", ColumnNames.dissolution)
        return df_result

    def getRightsIssueDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020023
        [주요사항보고서 주요정보::5.유상증자 결정]
        주요사항보고서(유상증자 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get rights issue decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "piicDecsn.json", ColumnNames.rights_issue_decision)
        return df_result

    def getBonusIssueDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020024
        [주요사항보고서 주요정보::6.무상증자 결정]
        주요사항보고서(무상증자 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get bonus issue decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "fricDecsn.json", ColumnNames.bonus_issue_decision)
        return df_result

    def getRightsBonusIssueDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020025
        [주요사항보고서 주요정보::7.유무상증자 결정]
        주요사항보고서(유무상증자 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get rights/bonus issue decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "pifricDecsn.json", ColumnNames.rights_bonus_issue_decision)
        return df_result

    def getCapitalReductionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020026
        [주요사항보고서 주요정보::8.감자 결정]
        주요사항보고서(감자 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get capital reduction decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "crDecsn.json", ColumnNames.capital_reduction_decision)
        return df_result

    def getBankManagementProcedureInitiateInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020027
        [주요사항보고서 주요정보::9.채권은행 등의 관리절차 개시]
        주요사항보고서(채권은행 등의 관리절차 개시) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get bank management procedure initiate info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "bnkMngtPcbg.json", ColumnNames.bank_management_procedure_initiate)
        return df_result

    def getLitigationInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020028
        [주요사항보고서 주요정보::10.소송 등의 제기]
        주요사항보고서(소송 등의 제기) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get litigation info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "lwstLg.json", ColumnNames.litigation)
        return df_result

    def getOverseasListingDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020029
        [주요사항보고서 주요정보::11.해외 증권시장 주권등 상장 결정]
        주요사항보고서(해외 증권시장 주권등 상장 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get overseas listing decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "ovLstDecsn.json", ColumnNames.overseas_listing_decision)
        return df_result

    def getOverseasDelistingDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020030
        [주요사항보고서 주요정보::12.해외 증권시장 주권등 상장폐지 결정]
        주요사항보고서(해외 증권시장 주권등 상장폐지 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get overseas delisting decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "ovDlstDecsn.json", ColumnNames.overseas_delisting_decision)
        return df_result

    def getOverseasListingInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020031
        [주요사항보고서 주요정보::13.해외 증권시장 주권등 상장]
        주요사항보고서(해외 증권시장 주권등 상장) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get overseas listing info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "ovLst.json", ColumnNames.overseas_listing)
        return df_result

    def getOverseasDelistingInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020032
        [주요사항보고서 주요정보::14.해외 증권시장 주권등 상장폐지]
        주요사항보고서(해외 증권시장 주권등 상장폐지) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get overseas delisting info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "ovDlst.json", ColumnNames.overseas_delisting)
        return df_result

    def getConvertibleBondsPublishDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020033
        [주요사항보고서 주요정보::15.전환사채권 발행결정]
        주요사항보고서(전환사채권 발행결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get convertible bonds publish decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "cvbdIsDecsn.json", ColumnNames.conv_bonds_publish_decision)
        return df_result

    def getBondWithWarrantPublishDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020034
        [주요사항보고서 주요정보::16.신주인수권부사채권 발행결정]
        주요사항보고서(신주인수권부사채권 발행결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get bond with warrant publish decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "bdwtIsDecsn.json", ColumnNames.bond_with_warrant_publish_decision)
        return df_result

    def getExchangeableBondsPublishDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020035
        [주요사항보고서 주요정보::17.교환사채권 발행결정]
        주요사항보고서(교환사채권 발행결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get exchangeable bonds publish decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "exbdIsDecsn.json", ColumnNames.exchangeable_bonds_publish_decision)
        return df_result

    def getBankManagementProcedureStopInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020036
        [주요사항보고서 주요정보::18.채권은행 등의 관리절차 중단]
        주요사항보고서(채권은행 등의 관리절차 중단) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get bank management procedure stop info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "bnkMngtPcsp.json", ColumnNames.bank_management_procedure_stop)
        return df_result

    def getAmortizationContingentConvertibleBondPublishDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020037
        [주요사항보고서 주요정보::19.상각형 조건부자본증권 발행결정]
        주요사항보고서(상각형 조건부자본증권 발행결정) 내에 주요 정보를 제공합니다.
        상각형 조건부자본증권 = 후순위채권

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get amortization contingent convertible bond publish decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "wdCocobdIsDecsn.json", ColumnNames.amortization_cocobond_publish_decision)
        return df_result

    def getAssetTransferPutbackOptionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020018
        [주요사항보고서 주요정보::20.자산양수도(기타), 풋백옵션]
        주요사항보고서(자산양수도(기타), 풋백옵션) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get asset transfer putback option info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "astInhtrfEtcPtbkOpt.json", ColumnNames.asset_transfer_putback_option)
        return df_result

    def getOtherCorpStockEquitySecuritiesTransferDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020047
        [주요사항보고서 주요정보::21.타법인 주식 및 출자증권 양도결정]
        주요사항보고서(타법인 주식 및 출자증권 양도결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get other corp stock equity securities transfer decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "otcprStkInvscrTrfDecsn.json", ColumnNames.other_corp_stock_transfer_decision)
        return df_result

    def getTangibleAssetsTransferDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020045
        [주요사항보고서 주요정보::22.유형자산 양도 결정]
        주요사항보고서(유형자산 양도 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get tangible assets transfer decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "tgastTrfDecsn.json", ColumnNames.tangible_transfer_decision)
        return df_result

    def getTangibleAssetsAcquisitionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020044
        [주요사항보고서 주요정보::23.유형자산 양수 결정]
        주요사항보고서(유형자산 양수 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get tangible assets acquisition decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "tgastInhDecsn.json", ColumnNames.tangible_acquisition_decision)
        return df_result

    def getOtherCorpStockEquitySecuritiesAcquisitionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020046
        [주요사항보고서 주요정보::24.타법인 주식 및 출자증권 양수결정]
        주요사항보고서(타법인 주식 및 출자증권 양수결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get other corp stock equity securities acquisition decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "otcprStkInvscrInhDecsn.json", ColumnNames.other_corp_stock_acq_decision)
        return df_result

    def getBusinessTransferDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020043
        [주요사항보고서 주요정보::25.영업양도 결정]
        주요사항보고서(영업양도 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get business transfer decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "bsnTrfDecsn.json", ColumnNames.business_transfer_decision)
        return df_result

    def getBusinessAcquisitionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020042
        [주요사항보고서 주요정보::26.영업양수 결정]
        주요사항보고서(영업양수 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get business acquisition decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "bsnInhDecsn.json", ColumnNames.business_acquisition_decision)
        return df_result

    def getTreasuryStockAcqusitionTrustContractTerminationDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020041
        [주요사항보고서 주요정보::27.자기주식취득 신탁계약 해지 결정]
        주요사항보고서(자기주식취득 신탁계약 해지 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get treasury stock acqusition contract termination decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "tsstkAqTrctrCcDecsn.json", ColumnNames.treasury_acq_contract_term_decision)
        return df_result

    def getTreasuryStockAcqusitionTrustContractConclusionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020040
        [주요사항보고서 주요정보::28.자기주식취득 신탁계약 체결 결정]
        주요사항보고서(자기주식취득 신탁계약 체결 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get treasury stock acqusition contract conclusion decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "tsstkAqTrctrCnsDecsn.json", ColumnNames.treasury_acq_contract_conc_decision)
        return df_result

    def getTreasuryStockDisposalDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020039
        [주요사항보고서 주요정보::29.자기주식 처분 결정]
        주요사항보고서(자기주식 처분 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get treasury stock disposal decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "tsstkDpDecsn.json", ColumnNames.treasury_stock_disposal_decision)
        return df_result

    def getTreasuryStockAcquisitionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020038
        [주요사항보고서 주요정보::30.자기주식 취득 결정]
        주요사항보고서(자기주식 취득 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get treasury stock acquisition decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "tsstkAqDecsn.json", ColumnNames.treasury_stock_acquisition_decision)
        return df_result

    def getStockExchangeTransferDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020053
        [주요사항보고서 주요정보::31.주식교환·이전 결정]
        주요사항보고서(주식교환·이전 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get stock exchange transfer decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "stkExtrDecsn.json", ColumnNames.stock_exchange_transfer)
        return df_result

    def getCompanyDivisionMergeDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020052
        [주요사항보고서 주요정보::32.회사분할합병 결정]
        주요사항보고서(회사분할합병 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get company division merge decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "cmpDvmgDecsn.json", ColumnNames.company_division_merge)
        return df_result

    def getCompanyDivisionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020051
        [주요사항보고서 주요정보::33.회사분할 결정]
        주요사항보고서(회사분할 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get company division decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "cmpDvDecsn.json", ColumnNames.company_division)
        return df_result

    def getCompanyMergeDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020050
        [주요사항보고서 주요정보::34.회사합병 결정]
        주요사항보고서(회사합병 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get company merge decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "cmpMgDecsn.json", ColumnNames.company_merge)
        return df_result

    def getDebenturesAcquisitionDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020048
        [주요사항보고서 주요정보::35.주권 관련 사채권 양수 결정]
        주요사항보고서(주권 관련 사채권 양수 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get debentures acquisition decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "stkrtbdInhDecsn.json", ColumnNames.debentures_acquisition)
        return df_result

    def getDebenturesTransferDecisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS005&apiId=2020049
        [주요사항보고서 주요정보::36.주권 관련 사채권 양도 결정]
        주요사항보고서(주권 관련 사채권 양도 결정) 내에 주요 정보를 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode})"
        self._log("get debentures transfer decision info " + info, LogType.Command)
        df_result = self._makeHighlightsDataFrameCommon(
            corpCode, dateBegin, dateEnd, "stkrtbdTrfDecsn.json", ColumnNames.debentures_transfer)
        return df_result

    """ 증권신고서 주요정보 API """

    def getStockExchangeInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020058
        [증권신고서 주요정보::1.주식의포괄적교환·이전]
        증권신고서(주식의포괄적교환·이전) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames (일반사항, 발행증권, 당사회사에관한사항)
        """
        self._log(f"get declaration info - stock exchange ({corpCode})", LogType.Command)
        params = self._getParamWithBeginEndDate(corpCode, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format("extrRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(ColumnNames.declaration_normal)
            df_stock = self._createEmptyDataFrame(ColumnNames.declaration_stock)
            df_detail = self._createEmptyDataFrame(ColumnNames.declaration_detail)
            return df_normal, df_stock, df_detail

        df_normal = self._makeDataFrameFromJsonGroup(json, '일반사항', ColumnNames.declaration_normal)
        df_stock = self._makeDataFrameFromJsonGroup(json, '발행증권', ColumnNames.declaration_stock)
        df_detail = self._makeDataFrameFromJsonGroup(json, '당사회사에관한사항', ColumnNames.declaration_detail)
        return df_normal, df_stock, df_detail

    def getMergeInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020057
        [증권신고서 주요정보::2.합병]
        증권신고서(합병) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames (일반사항, 발행증권, 당사회사에관한사항)
        """
        self._log(f"get declaration info - merge ({corpCode})", LogType.Command)
        params = self._getParamWithBeginEndDate(corpCode, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format("mgRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(ColumnNames.declaration_normal)
            df_stock = self._createEmptyDataFrame(ColumnNames.declaration_stock)
            df_detail = self._createEmptyDataFrame(ColumnNames.declaration_detail)
            return df_normal, df_stock, df_detail

        df_normal = self._makeDataFrameFromJsonGroup(json, '일반사항', ColumnNames.declaration_normal)
        df_stock = self._makeDataFrameFromJsonGroup(json, '발행증권', ColumnNames.declaration_stock)
        df_detail = self._makeDataFrameFromJsonGroup(json, '당사회사에관한사항', ColumnNames.declaration_detail)
        return df_normal, df_stock, df_detail

    def getDepositaryReceiptInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020056
        [증권신고서 주요정보::3.증권예탁증권]
        증권신고서(증권예탁증권) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames (일반사항, 증권의종류, 인수인정보, 자금의사용목적, 매출인에관한사항)
        """
        self._log(f"get declaration info - depositary receipt ({corpCode})", LogType.Command)
        params = self._getParamWithBeginEndDate(corpCode, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format("stkdpRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(ColumnNames.declaration_normal)
            df_type = self._createEmptyDataFrame(ColumnNames.declaration_type)
            df_takeover = self._createEmptyDataFrame(ColumnNames.declaration_takeover)
            df_purpose = self._createEmptyDataFrame(ColumnNames.declaration_purpose)
            df_seller = self._createEmptyDataFrame(ColumnNames.declaration_seller)
            return df_normal, df_type, df_takeover, df_purpose, df_seller

        df_normal = self._makeDataFrameFromJsonGroup(json, '일반사항', ColumnNames.declaration_normal)
        df_type = self._makeDataFrameFromJsonGroup(json, '증권의종류', ColumnNames.declaration_type)
        df_takeover = self._makeDataFrameFromJsonGroup(json, '인수인정보', ColumnNames.declaration_takeover)
        df_purpose = self._makeDataFrameFromJsonGroup(json, '자금의사용목적', ColumnNames.declaration_purpose)
        df_seller = self._makeDataFrameFromJsonGroup(json, '매출인에관한사항', ColumnNames.declaration_seller)
        return df_normal, df_type, df_takeover, df_purpose, df_seller

    def getDebtSecuritiesInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020055
        [증권신고서 주요정보::4.채무증권]
        증권신고서(채무증권) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames (일반사항, 인수인정보, 자금의사용목적, 매출인에관한사항)
        """
        self._log(f"get declaration info - dept securites ({corpCode})", LogType.Command)
        params = self._getParamWithBeginEndDate(corpCode, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format("bdRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(ColumnNames.declaration_normal)
            df_takeover = self._createEmptyDataFrame(ColumnNames.declaration_takeover)
            df_purpose = self._createEmptyDataFrame(ColumnNames.declaration_purpose)
            df_seller = self._createEmptyDataFrame(ColumnNames.declaration_seller)
            return df_normal, df_takeover, df_purpose, df_seller

        df_normal = self._makeDataFrameFromJsonGroup(json, '일반사항', ColumnNames.declaration_normal)
        df_takeover = self._makeDataFrameFromJsonGroup(json, '인수인정보', ColumnNames.declaration_takeover)
        df_purpose = self._makeDataFrameFromJsonGroup(json, '자금의사용목적', ColumnNames.declaration_purpose)
        df_seller = self._makeDataFrameFromJsonGroup(json, '매출인에관한사항', ColumnNames.declaration_seller)
        return df_normal, df_takeover, df_purpose, df_seller

    def getEquitySecuritiesInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020054
        [증권신고서 주요정보::5.지분증권]
        증권신고서(지분증권) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames
                 (일반사항, 증권의 종류, 인수인정보, 자금의사용목적, 매출인에관한사항, 일반청약자환매청구권)
        """
        self._log(f"get declaration info - equity securites ({corpCode})", LogType.Command)
        params = self._getParamWithBeginEndDate(corpCode, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format("estkRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(ColumnNames.declaration_normal)
            df_type = self._createEmptyDataFrame(ColumnNames.declaration_type)
            df_takeover = self._createEmptyDataFrame(ColumnNames.declaration_takeover)
            df_purpose = self._createEmptyDataFrame(ColumnNames.declaration_purpose)
            df_seller = self._createEmptyDataFrame(ColumnNames.declaration_seller)
            df_putback = self._createEmptyDataFrame(ColumnNames.declaration_putback)
            return df_normal, df_type, df_takeover, df_purpose, df_seller, df_putback

        df_normal = self._makeDataFrameFromJsonGroup(json, '일반사항', ColumnNames.declaration_normal)
        df_type = self._makeDataFrameFromJsonGroup(json, '증권의종류', ColumnNames.declaration_type)
        df_takeover = self._makeDataFrameFromJsonGroup(json, '인수인정보', ColumnNames.declaration_takeover)
        df_purpose = self._makeDataFrameFromJsonGroup(json, '자금의사용목적', ColumnNames.declaration_purpose)
        df_seller = self._makeDataFrameFromJsonGroup(json, '매출인에관한사항', ColumnNames.declaration_seller)
        df_putback = self._makeDataFrameFromJsonGroup(json, '일반청약자환매청구권', ColumnNames.declaration_putback)
        return df_normal, df_type, df_takeover, df_purpose, df_seller, df_putback

    def getDivisionInfo(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020059
        [증권신고서 주요정보::6.분할]
        증권신고서(분할) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames (일반사항, 발행증권, 당사회사에관한사항)
        """
        self._log(f"get declaration info - division ({corpCode})", LogType.Command)
        params = self._getParamWithBeginEndDate(corpCode, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format("dvRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ApiResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(ColumnNames.declaration_normal)
            df_stock = self._createEmptyDataFrame(ColumnNames.declaration_stock)
            df_detail = self._createEmptyDataFrame(ColumnNames.declaration_detail)
            return df_normal, df_stock, df_detail

        df_normal = self._makeDataFrameFromJsonGroup(json, '일반사항', ColumnNames.declaration_normal)
        df_stock = self._makeDataFrameFromJsonGroup(json, '발행증권', ColumnNames.declaration_stock)
        df_detail = self._makeDataFrameFromJsonGroup(json, '당사회사에관한사항', ColumnNames.declaration_detail)
        return df_normal, df_stock, df_detail
