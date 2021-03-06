# Author: Yogyui
import os
import io
import re
import time
import shutil
import pickle
import zipfile
import datetime
import requests
import lxml.html
import urllib.parse
import pandas as pd
import logging.handlers
from enum import Enum, auto
from lxml import etree, html
from typing import List, Union, Tuple
from requests_html import HTMLSession
from config import OpenDartConfiguration
from define import *


url_opendart = 'https://opendart.fss.or.kr/api/{}'


def convertTagToDict(tag: etree.Element) -> dict:
    conv = {}
    for child in list(tag):
        conv[child.tag] = child.text
    return conv


class ResponseException(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
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


class OpenDart:
    _df_corplist: pd.DataFrame = None
    _logger_console: logging.Logger
    _write_log_console_to_file: bool = False
    _rename_dataframe_column_names: bool = True

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

        self._config = OpenDartConfiguration()

        if api_key is not None:
            self.setApiKey(api_key)
        self.loadCorporationDataFrame()

    def _initLoggerConsole(self):
        self._logger_console = logging.getLogger('opendart_console')
        filepath = os.path.join(self._path_log_dir, 'console.log')
        maxBytes = 100 * 1024 * 1024
        handler = logging.handlers.RotatingFileHandler(filepath, maxBytes=maxBytes, backupCount=10, encoding='utf-8')
        formatter = logging.Formatter('[%(asctime)s]%(message)s')
        handler.setFormatter(formatter)
        self._logger_console.addHandler(handler)
        self._logger_console.setLevel(logging.DEBUG)

    def _log(self, message: str, logType: LogType):
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

    def isEnableWriteLogConsoleToFile(self) -> bool:
        return self._write_log_console_to_file

    def setEnableWriteLogConsoleToFile(self, enable: bool):
        self._write_log_console_to_file = enable

    def isEnableRenameDataframeColumnNames(self) -> bool:
        return self._rename_dataframe_column_names

    def setEnableRenameDataframeColumnNames(self, enable: bool):
        self._rename_dataframe_column_names = enable

    def setApiKey(self, key: str):
        self._config.api_key = key
        self._log(f"set api key: {self._config.api_key}", LogType.Command)
        self._config.saveToLocalFile()
        self.loadCorporationDataFrame()

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
            dest_path = os.path.join(self._path_data_dir, dest_dir)
            zf.extractall(dest_path)
            zf.close()
            self._log(f"extracted {len(filenames)} file(s) to {dest_path}", LogType.Info)
            return filenames
        except zipfile.BadZipfile:
            self._parseResultFromResponse(content)

    @staticmethod
    def _parseResultFromResponse(content: bytes):
        node_result = etree.fromstring(content)
        node_status = node_result.find('status')
        node_message = node_result.find('message')
        status_code = int(node_status.text)
        message = node_message.text
        if status_code != 0:
            raise ResponseException(status_code, message)

    def clearDocumentFilesFromDataPath(self):
        doc_extensions = ['.xml', '.html']
        files_in_datapath = os.listdir(self._path_data_dir)
        targets = list(filter(lambda x: os.path.splitext(x)[-1] in doc_extensions, files_in_datapath))
        if len(targets) > 0:
            target_paths = [os.path.join(self._path_data_dir, x) for x in targets]
            for filepath in target_paths:
                os.remove(filepath)
            self._log(f"removed {len(target_paths)} document files", LogType.Info)

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

    @staticmethod
    def _checkResponseStatus(json_obj: dict):
        status = json_obj.get('status')
        message = json_obj.get('message')
        if status != '000':
            raise ResponseException(int(status), message)

    @staticmethod
    def _createEmptyDataFrame(column_names: Union[List[str], dict]) -> pd.DataFrame:
        df_result = pd.DataFrame()
        if isinstance(column_names, dict):
            column_names = list(column_names.values())
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

    def _serializeCorporationDataFrame(self):
        with open(self._path_corp_df_pkl_file, 'wb') as fp:
            pickle.dump(self._df_corplist, fp)

    """ 공시정보 API """

    def searchDocument(
            self, corpCode: str = None, dateEnd: Union[str, datetime.date] = datetime.datetime.now().date(),
            dateBegin: Union[str, datetime.date] = None, onlyLastReport: bool = True, pageNumber: int = 1,
            pageCount: int = 100, pbType: str = None, pbTypeDetail: str = None, recursive: bool = False
    ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001
        [공시정보::1.공시검색]
        공시 유형별, 회사별, 날짜별 등 여러가지 조건으로 공시보고서 검색기능을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param dateEnd: 검색종료 접수일자(YYYYMMDD), 기본값 = 호출당일
        :param dateBegin: 검색시작 접수일자(YYYYMMDD)
        :param onlyLastReport: 최종보고서만 검색여부, 기본값 = False(정정이 있는 경우 최종정정만 검색)
        :param pageNumber: 페이지 번호, 기본값 = 1
        :param pageCount: 페이지당 건수, 기본값 = 100 (범위 = 1 ~ 100)
        :param pbType: 공시유형 (define -> dict_pblntf_ty 참고)
        :param pbTypeDetail: 공시유형 (define -> dict_pblntf_detail_ty 참고)
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
        params['last_reprt_at'] = 'Y' if onlyLastReport else 'N'
        params['page_no'] = max(1, pageNumber)
        params['page_count'] = max(1, min(100, pageCount))
        if pbType is not None:
            params['pblntf_ty'] = pbType
        if pbTypeDetail is not None:
            params['pblntf_detail_ty'] = pbTypeDetail
        # params['corp_cls']  # TODO:

        json = self._requestAndGetJson(url_opendart.format("list.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.search_document)

        page_no = json.get('page_no')
        total_page = json.get('total_page')
        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        if not recursive:  # loop query more than 1 page - recursive call
            for page in range(page_no + 1, total_page + 1):
                df_new = self.searchDocument(corpCode, dateEnd, dateBegin, onlyLastReport,
                                             page, pageCount, pbType, pbTypeDetail, recursive=True)
                df_result = df_result.append(df_new)

        if self._rename_dataframe_column_names:
            df_result.rename(columns=ColumnNames.search_document, inplace=True)
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
        self._log(f"get company information (corp code: {corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        json = self._requestAndGetJson(url_opendart.format("company.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
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
        params = {'rcept_no': document_no}
        if reload:
            self._removeDocumentRawFileInLocal(document_no)
        if not self._isDocumentRawFileExistInLocal(document_no):
            self._log(f"download document raw file (doc no: {document_no})", LogType.Command)
            try:
                self._requestAndExtractZipFile(url_opendart.format("document.xml"), **params)
            except ResponseException as e:
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
            self._log("load corporation list as dataframe", LogType.Command)
            self._setReadyForCorporationDataFramePickleFile(reload)
            if not self._tryLoadingCorporationDataFrameFromPickleFile():
                try:
                    self._requestAndExtractZipFile(url_opendart.format("corpCode.xml"))
                except ResponseException as e:
                    self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
                    self._df_corplist = self._createEmptyDataFrame(ColumnNames.corp_code)
                else:
                    self._makeCorporationDataFrameFromFile()
                self._serializeCorporationDataFrame()
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

    def readDocumentRawFileAsString(
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
            self, document_no: str, reload: bool = False
    ) -> str:
        if reload:
            self._removeDocumentHtmlFileInLocal(document_no)
        if not self._isDocumentHtmlFileExistInLocal(document_no):
            self._log(f"download document as html file (doc no: {document_no})", LogType.Command)
            url = "https://dart.fss.or.kr/dsaf001/main.do?rcpNo={}".format(document_no)
            response_viewer = self._requestAndRender(url)
            url_doc_page = self._getDocumentUrlFromViewerResponse(response_viewer)
            url_doc_page_modified = self._modifyQueryValueOfDocumentUrl(url_doc_page)
            response_document = self._requestAndRender(url_doc_page_modified)
            encoding = response_document.html.encoding
            html_element = self._modifyTagAttributesOfDocumentResponse(response_document)
            self._saveElementToLocalHtmlFile(html_element, document_no, encoding)
        path_dest = os.path.join(self._path_data_dir, f'{document_no}.html')
        return path_dest

    def loadDocumentHtmlFileAsElementTree(
            self, document_no: str, reload: bool = False
    ) -> etree.ElementTree:
        self.downloadDocumentAsHtmlFile(document_no, reload)
        path_file = os.path.join(self._path_data_dir, f'{document_no}.html')
        tree = html.parse(path_file)
        return tree

    def loadDocumentHtmlFileAsText(
            self, document_no: str, reload: bool = False
    ) -> str:
        tree = self.loadDocumentHtmlFileAsElementTree(document_no, reload)
        encoding = tree.docinfo.encoding
        raw = html.tostring(tree, encoding=encoding)
        text = raw.decode(encoding=encoding)
        return text

    def getCompanyInformationByName(
            self, name: str, match_exact: bool = False
    ) -> pd.DataFrame:
        search_result = self.searchCorporationCodeWithName(name, match_exact)
        df_result = pd.DataFrame()
        for elem in search_result:
            df_elem = self.getCompanyInformation(elem[1])
            df_result = df_result.append(df_elem)
        return df_result

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
                    result = source[:span[0]] + '&lt;' + source[span[0]+1:span[1]-1] + '&gt;' + source[span[1]:]
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

    def _requestAndRender(self, url: str) -> requests.models.Response:
        session = HTMLSession()

        response = session.get(url)
        message = f"<status:{response.status_code}> "
        message += f"<elapsed:{response.elapsed.microseconds/1000}ms> "
        message += f"<encoding:{response.html.encoding}> "
        message += f"<url:{response.url}> "
        self._log(message, LogType.API)

        tm_start = time.perf_counter()
        response.html.render()
        elapsed = time.perf_counter() - tm_start
        self._log(f"render done (elapsed: {elapsed} sec)", LogType.Info)

        session.close()
        return response

    @staticmethod
    def _getDocumentUrlFromViewerResponse(response: requests.models.Response):
        element = response.html.lxml
        tag_iframe = element.get_element_by_id("ifrm")
        attrib_src = tag_iframe.attrib.get('src')
        url = "https://dart.fss.or.kr{}".format(attrib_src)
        return url

    @staticmethod
    def _modifyQueryValueOfDocumentUrl(url: str) -> str:
        url_parsed = urllib.parse.urlparse(url)
        queries = url_parsed.query.split('&')
        queries_split = [x.split('=') for x in queries]
        queries_dict = {}
        for q in queries_split:
            queries_dict[q[0]] = q[1]
        queries_dict['offset'] = '0'
        queries_dict['length'] = '0'
        queries = '&'.join([f'{x[0]}={x[1]}' for x in queries_dict.items()])
        url_parsed = url_parsed._replace(query=queries)
        return url_parsed.geturl()

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

    """ 사업보고서 주요정보 API """

    def _makeBusinessReportDataFrameCommon(
            self, corp_code: str, year: int, rpt_code: str, api: str, col_names: dict
    ) -> pd.DataFrame:
        params = {'corp_code': corp_code, 'bsns_year': str(max(2015, year)), 'reprt_code': rpt_code}
        json = self._requestAndGetJson(url_opendart.format(api), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(col_names)
        df_result = self._makeDataFrameFromJsonList(json, col_names)
        return df_result

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
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get single financial information " + info, LogType.Command)
        params = {'corp_code': corpCode, 'bsns_year': str(max(2015, year)), 'reprt_code': rptcode}
        json = self._requestAndGetJson(url_opendart.format("fnlttSinglAcnt.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.financial)

        df_result = self._makeDataFrameFromJsonList(json, ColumnNames.financial)
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
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        info = f"(corp code: {corpCode}, year: {year}, report code: {rptcode})"
        self._log("get multiple financial information " + info, LogType.Command)
        params = {'corp_code': ','.join(corpCode), 'bsns_year': str(max(2015, year)), 'reprt_code': rptcode}
        json = self._requestAndGetJson(url_opendart.format("fnlttMultiAcnt.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.financial)

        df_result = self._makeDataFrameFromJsonList(json, ColumnNames.financial)
        return df_result

    def downloadFinancialStatementsRawFile(
            self, receiptNo: str, reportCode: Union[ReportCode, str], reload: bool = False
    ):
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019019
        [상장기업 재무정보::3.재무제표 원본파일(XBRL)]
        상장법인이 제출한 정기보고서 내에 XBRL재무제표의 원본파일(XBRL)을 제공합니다.

        :param receiptNo: 접수번호
        :param reportCode: 보고서 코드
        :param reload: 디렉터리가 존재할 경우 삭제하고 다시 다운로드받을 지 여부
        """
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        if reload:
            self._removeFinancialStatementsDirInLocal(receiptNo, rptcode)
        if not self._isFinancialStatementsDirExistInLocal(receiptNo, rptcode):
            info = f"(receipt no: {receiptNo}, report code: {rptcode})"
            self._log("download financial statements raw file " + info, LogType.Command)
            params = {'rcept_no': receiptNo, 'reprt_code': rptcode}
            dest_dir = f'fs_{receiptNo}_{rptcode}'
            try:
                self._requestAndExtractZipFile(url_opendart.format("fnlttXbrl.xml"), dest_dir, **params)
            except ResponseException as e:
                self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)

    # TODO: 단일회사 전체 재무제표, XBRL택사노미재무제표양식

    def _isFinancialStatementsDirExistInLocal(self, receiptNo: str, reportCode: Union[ReportCode, str]) -> bool:
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        path_dir = os.path.join(self._path_data_dir, f'fs_{receiptNo}_{rptcode}')
        return os.path.isdir(path_dir)

    def _removeFinancialStatementsDirInLocal(self, receiptNo: str, reportCode: Union[ReportCode, str]):
        rptcode = reportCode.value if isinstance(reportCode, ReportCode) else reportCode
        path_dir = os.path.join(self._path_data_dir, f'fs_{receiptNo}_{rptcode}')
        if os.path.isdir(path_dir):
            shutil.rmtree(path_dir)

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
        self._log(f"get major stock information (corp code: {corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        json = self._requestAndGetJson(url_opendart.format("majorstock.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
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
        self._log(f"get executive stock information (corp code: {corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        json = self._requestAndGetJson(url_opendart.format("elestock.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(ColumnNames.executive_stock)

        df_result = self._makeDataFrameFromJsonList(json, ColumnNames.executive_stock)
        return df_result

    """ 주요사항보고서 주요정보 API """

    @staticmethod
    def _getParamWithBeginEndDate(
            corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> dict:
        params = {'corp_code': corpCode}
        if isinstance(dateBegin, datetime.date):
            params['bgn_de'] = dateBegin.strftime('%Y%m%d')
        else:
            params['bgn_de'] = dateBegin
        if isinstance(dateEnd, datetime.date):
            params['end_de'] = dateEnd.strftime('%Y%m%d')
        else:
            params['end_de'] = dateEnd
        return params

    def _makeHighlightsDataFrameCommon(
            self, corp_code: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date],
            api: str, col_names: dict
    ) -> pd.DataFrame:
        params = self._getParamWithBeginEndDate(corp_code, dateBegin, dateEnd)
        json = self._requestAndGetJson(url_opendart.format(api), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(col_names)
        df_result = self._makeDataFrameFromJsonList(json, col_names)
        return df_result

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

    # TODO: 감자 결정 ~

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
        except ResponseException as e:
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
        except ResponseException as e:
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
        except ResponseException as e:
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
        except ResponseException as e:
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
        except ResponseException as e:
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
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(ColumnNames.declaration_normal)
            df_stock = self._createEmptyDataFrame(ColumnNames.declaration_stock)
            df_detail = self._createEmptyDataFrame(ColumnNames.declaration_detail)
            return df_normal, df_stock, df_detail

        df_normal = self._makeDataFrameFromJsonGroup(json, '일반사항', ColumnNames.declaration_normal)
        df_stock = self._makeDataFrameFromJsonGroup(json, '발행증권', ColumnNames.declaration_stock)
        df_detail = self._makeDataFrameFromJsonGroup(json, '당사회사에관한사항', ColumnNames.declaration_detail)
        return df_normal, df_stock, df_detail
