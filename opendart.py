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

    def setEnableWriteLogConsoleToFile(self, enable: bool):
        self._write_log_console_to_file = enable

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
            self._df_corplist = self._createEmptyDataFrame(columns_corp_code)

        self._df_corplist.rename(columns=columns_corp_code, inplace=True)
        # change 'modify_date' type (str -> datetime)
        self._df_corplist['최종변경일자'] = pd.to_datetime(self._df_corplist['최종변경일자'], format='%Y%m%d')

    def _serializeCorporationDataFrame(self):
        with open(self._path_corp_df_pkl_file, 'wb') as fp:
            pickle.dump(self._df_corplist, fp)

    """ 공시정보 API """
    def loadCorporationDataFrame(self, reload: bool = False) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003
        [공시정보::고유번호]
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
                    self._df_corplist = self._createEmptyDataFrame(columns_corp_code)
                else:
                    self._makeCorporationDataFrameFromFile()
                self._serializeCorporationDataFrame()
        return self._df_corplist

    def searchCorporationCodeWithName(self, name: str, match_exact: bool = False) -> pd.DataFrame:
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

    def downloadDocumentRawFile(self, document_no: str, reload: bool = False):
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019003
        [공시정보::공시서류원본파일]
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

    def readDocumentRawFileAsString(self, document_no: str, reload: bool = False) -> str:
        self.downloadDocumentRawFile(document_no, reload)
        path_file = os.path.join(self._path_data_dir, f'{document_no}.xml')
        raw_string = ''
        if os.path.isfile(path_file):
            with open(path_file, 'r', encoding='utf-8') as fp:
                raw_string = fp.read()
        return raw_string

    def searchDocument(self, corpCode: str = None, dateEnd: Union[str, datetime.date] = datetime.datetime.now().date(),
                       dateBegin: Union[str, datetime.date] = None, onlyLastReport: bool = True, pageNumber: int = 1,
                       pageCount: int = 100, pbType: str = None, pbTypeDetail: str = None, recursive: bool = False
                       ) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001
        [공시정보::공시검색]
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
            return self._createEmptyDataFrame(columns_search_document)

        page_no = json.get('page_no')
        total_page = json.get('total_page')
        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        if not recursive:  # loop query more than 1 page - recursive call
            for page in range(page_no + 1, total_page + 1):
                df_new = self.searchDocument(corpCode, dateEnd, dateBegin, onlyLastReport,
                                             page, pageCount, pbType, pbTypeDetail, recursive=True)
                df_result = df_result.append(df_new)

        df_result.rename(columns=columns_search_document, inplace=True)

        return df_result

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

    def downloadDocumentAsHtmlFile(self, document_no: str, reload: bool = False):
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

    def loadDocumentHtmlFileAsElementTree(self, document_no: str, reload: bool = False) -> etree.ElementTree:
        self.downloadDocumentAsHtmlFile(document_no, reload)
        path_file = os.path.join(self._path_data_dir, f'{document_no}.html')
        tree = html.parse(path_file)
        return tree

    def loadDocumentHtmlFileAsText(self, document_no: str, reload: bool = False) -> str:
        tree = self.loadDocumentHtmlFileAsElementTree(document_no, reload)
        encoding = tree.docinfo.encoding
        raw = html.tostring(tree, encoding=encoding)
        text = raw.decode(encoding=encoding)
        return text

    def getCompanyInformation(self, corpCode: str) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002
        [공시정보::기업개황]
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
            return self._createEmptyDataFrame(columns_company_info)

        df_result = pd.DataFrame([json])
        df_result.pop("status")
        df_result.pop("message")
        df_result.rename(columns=columns_company_info, inplace=True)

        return df_result

    def getCompanyInformationByName(self, name: str, match_exact: bool = False) -> pd.DataFrame:
        search_result = self.searchCorporationCodeWithName(name, match_exact)
        df_result = pd.DataFrame()
        for elem in search_result:
            df_elem = self.getCompanyInformation(elem[1])
            df_result = df_result.append(df_elem)
        return df_result

    """ 지분공시 종합정보 API """
    def getMajorStockInformation(self, corpCode: str) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019021
        [지분공시 종합정보::대량보유 상황보고]
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
            return self._createEmptyDataFrame(columns_major_stock_info)

        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        df_result.rename(columns=columns_major_stock_info, inplace=True)

        return df_result

    def getExecutiveStockInformation(self, corpCode: str) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/main.do?apiGrpCd=DS004
        [지분공시 종합정보::임원ㆍ주요주주 소유보고]
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
            return self._createEmptyDataFrame(columns_executive_stock_info)

        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        df_result.rename(columns=columns_executive_stock_info, inplace=True)

        return df_result

    """ 상장기업 재무정보 API """
    # TODO: 단일회사 전체 재무제표, XBRL택사노미재무제표양식
    def getSingleFinancialInformation(self, corpCode: str, year: int, reportCode: ReportCode) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019016
        [상장기업 재무정보::단일회사 주요계정]
        상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 주요계정과목(재무상태표, 손익계산서)을 제공합니다.

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode}, year: {year}, report code: {reportCode.value})"
        self._log("get single financial information " + info, LogType.Command)
        params = {'corp_code': corpCode, 'bsns_year': str(max(2015, year)), 'reprt_code': reportCode.value}
        json = self._requestAndGetJson(url_opendart.format("fnlttSinglAcnt.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(columns_financial_info)

        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        df_result.rename(columns=columns_financial_info, inplace=True)

        return df_result

    def getMultiFinancialInformation(self, corpCode: List[str], year: int, reportCode: ReportCode) -> pd.DataFrame:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019017
        [상장기업 재무정보::다중회사 주요계정]
        상장법인(금융업 제외)이 제출한 정기보고서 내에 XBRL재무제표의 주요계정과목(재무상태표, 손익계산서)을 제공합니다.
        (상장법인 복수조회 가능)

        :param corpCode: 공시대상회사의 고유번호(8자리)
        :param year: 사업연도, 2015년 이후 부터 정보제공
        :param reportCode: 보고서 코드
        :return: pandas DataFrame
        """
        info = f"(corp code: {corpCode}, year: {year}, report code: {reportCode.value})"
        self._log("get multiple financial information " + info, LogType.Command)
        params = {'corp_code': ','.join(corpCode), 'bsns_year': str(max(2015, year)), 'reprt_code': reportCode.value}
        json = self._requestAndGetJson(url_opendart.format("fnlttMultiAcnt.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            return self._createEmptyDataFrame(columns_financial_info)

        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        df_result.rename(columns=columns_financial_info, inplace=True)

        return df_result

    def _isFinancialStatementsDirExistInLocal(self, receiptNo: str, reportCode: ReportCode) -> bool:
        path_dir = os.path.join(self._path_data_dir, f'fs_{receiptNo}_{reportCode.value}')
        return os.path.isdir(path_dir)

    def _removeFinancialStatementsDirInLocal(self, receiptNo: str, reportCode: ReportCode):
        path_dir = os.path.join(self._path_data_dir, f'fs_{receiptNo}_{reportCode.value}')
        if os.path.isdir(path_dir):
            shutil.rmtree(path_dir)

    def downloadFinancialStatementsRawFile(self, receiptNo: str, reportCode: ReportCode, reload: bool = False):
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019019
        [상장기업 재무정보::재무제표 원본파일(XBRL)]
        상장법인이 제출한 정기보고서 내에 XBRL재무제표의 원본파일(XBRL)을 제공합니다.

        :param receiptNo: 접수번호
        :param reportCode: 보고서 코드
        :param reload: 디렉터리가 존재할 경우 삭제하고 다시 다운로드받을 지 여부
        """
        if reload:
            self._removeFinancialStatementsDirInLocal(receiptNo, reportCode)
        if not self._isFinancialStatementsDirExistInLocal(receiptNo, reportCode):
            info = f"(receipt no: {receiptNo}, report code: {reportCode.value})"
            self._log("download financial statements raw file " + info, LogType.Command)
            params = {'rcept_no': receiptNo, 'reprt_code': reportCode.value}
            dest_dir = f'fs_{receiptNo}_{reportCode.value}'
            try:
                self._requestAndExtractZipFile(url_opendart.format("fnlttXbrl.xml"), dest_dir, **params)
            except ResponseException as e:
                self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)

    """ 증권신고서 주요정보 API """
    # TODO: 증권예탁증권, 채무증권, 지분증권, 분할
    def getDeclarationInfoStockExchange(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020058
        [증권신고서 주요정보::주식의포괄적교환·이전]
        증권신고서(주식의포괄적교환·이전) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames (일반사항, 발행증권, 당사회사에관한사항)
        """
        self._log(f"get declaration info - stock exchange ({corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        if isinstance(dateBegin, datetime.date):
            params['bgn_de'] = dateBegin.strftime('%Y%m%d')
        else:
            params['bgn_de'] = dateBegin
        if isinstance(dateEnd, datetime.date):
            params['end_de'] = dateEnd.strftime('%Y%m%d')
        else:
            params['end_de'] = dateEnd
        json = self._requestAndGetJson(url_opendart.format("extrRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(columns_declaration_info_normal)
            df_stock = self._createEmptyDataFrame(columns_declaration_info_stock)
            df_detail = self._createEmptyDataFrame(columns_declaration_info_detail)
            return df_normal, df_stock, df_detail

        group_normal = list(filter(lambda x: x.get('title') == '일반사항', json.get('group')))[0]
        group_stock = list(filter(lambda x: x.get('title') == '발행증권', json.get('group')))[0]
        group_detail = list(filter(lambda x: x.get('title') == '당사회사에관한사항', json.get('group')))[0]

        data_list_normal = group_normal.get('list')
        df_normal = pd.DataFrame(data_list_normal)
        df_normal.rename(columns=columns_declaration_info_normal, inplace=True)
        data_list_stock = group_stock.get('list')
        df_stock = pd.DataFrame(data_list_stock)
        df_stock.rename(columns=columns_declaration_info_stock, inplace=True)
        data_list_detail = group_detail.get('list')
        df_detail = pd.DataFrame(data_list_detail)
        df_detail.rename(columns=columns_declaration_info_detail, inplace=True)

        return df_normal, df_stock, df_detail

    def getDeclarationInfoMerge(
            self, corpCode: str, dateBegin: Union[str, datetime.date], dateEnd: Union[str, datetime.date]
    ) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """
        https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS006&apiId=2020057
        [증권신고서 주요정보::합병]
        증권신고서(합병) 내에 요약 정보를 제공합니다.

        :param corpCode: 고유번호
        :param dateBegin: 시작일
        :param dateEnd: 종료일
        :return: tuple of pandas DataFrames (일반사항, 발행증권, 당사회사에관한사항)
        """
        self._log(f"get declaration info - stock exchange ({corpCode})", LogType.Command)
        params = {'corp_code': corpCode}
        if isinstance(dateBegin, datetime.date):
            params['bgn_de'] = dateBegin.strftime('%Y%m%d')
        else:
            params['bgn_de'] = dateBegin
        if isinstance(dateEnd, datetime.date):
            params['end_de'] = dateEnd.strftime('%Y%m%d')
        else:
            params['end_de'] = dateEnd
        json = self._requestAndGetJson(url_opendart.format("mgRs.json"), **params)
        try:
            self._checkResponseStatus(json)
        except ResponseException as e:
            self._log(f"response exception({e.status_code}) - {e.message}", LogType.Error)
            df_normal = self._createEmptyDataFrame(columns_declaration_info_normal)
            df_stock = self._createEmptyDataFrame(columns_declaration_info_stock)
            df_detail = self._createEmptyDataFrame(columns_declaration_info_detail)
            return df_normal, df_stock, df_detail

        group_normal = list(filter(lambda x: x.get('title') == '일반사항', json.get('group')))[0]
        group_stock = list(filter(lambda x: x.get('title') == '발행증권', json.get('group')))[0]
        group_detail = list(filter(lambda x: x.get('title') == '당사회사에관한사항', json.get('group')))[0]

        data_list_normal = group_normal.get('list')
        df_normal = pd.DataFrame(data_list_normal)
        df_normal.rename(columns=columns_declaration_info_normal, inplace=True)
        data_list_stock = group_stock.get('list')
        df_stock = pd.DataFrame(data_list_stock)
        df_stock.rename(columns=columns_declaration_info_stock, inplace=True)
        data_list_detail = group_detail.get('list')
        df_detail = pd.DataFrame(data_list_detail)
        df_detail.rename(columns=columns_declaration_info_detail, inplace=True)

        return df_normal, df_stock, df_detail

    """ 사업보고서 주요정보 API """
    # TODO:

    """ 주요사항 보고서 주요정보 API """
    # TODO:
