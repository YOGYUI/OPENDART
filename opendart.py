# Author: Yogyui
import os
import io
import re
import time
import datetime
import pickle
import requests
import zipfile
import pandas as pd
import xml.etree.ElementTree as ET
from typing import List


def convertTagToDict(tag: ET.Element) -> dict:
    conv = {}
    for child in list(tag):
        conv[child.tag] = child.text
    return conv


class OpenDart:
    api_key: str
    df_corplist: pd.DataFrame
    path_data: str
    path_corp_df_pkl: str
    path_config: str
    path_config_xmlfile: str

    def __init__(self):
        curpath = os.path.dirname(os.path.abspath(__file__))
        self.path_data = os.path.join(curpath, 'Data')
        if not os.path.isdir(self.path_data):
            os.mkdir(self.path_data)
        self.path_config = os.path.join(curpath, 'Config')
        if not os.path.isdir(self.path_config):
            os.mkdir(self.path_config)
        self.path_corp_df_pkl = os.path.join(self.path_data, 'Corplist.pkl')
        self.path_config_xmlfile = os.path.join(self.path_config, 'opendart.xml')
        self.loadConfigurationFromConfigXmlFile()
        self.getCorporationDataFrame()
        self.xml_replace_set = [
            ('&cr;', '&#13;'),
            ('M&A', 'M&amp;A'),
            ('R&D', 'R&amp;D'),
            ('S&P', 'S&amp;P')
        ]

    def setOpenDartApiKey(self, key: str):
        self.api_key = key

    def loadConfigurationFromConfigXmlFile(self):
        pass

    def saveConfigurationToConfigXmlFile(self):
        pass

    def makeRequestParameter(self, **kwargs) -> dict:
        params: dict = {'crtfc_key': self.api_key}
        params.update(kwargs)
        return params

    def requestAndExtractZipFile(self, url: str, **kwargs) -> List[str]:
        content = self.requestAndGetContent(url, **kwargs)
        iostream = io.BytesIO(content)
        zf = zipfile.ZipFile(iostream)
        info = zf.infolist()
        filenames = [x.filename for x in info]
        zf.extractall(self.path_data)
        zf.close()
        return filenames

    def removeDocumentFilesFromDataPath(self):
        doc_extensions = ['.xml', '.html']
        files_in_datapath = os.listdir(self.path_data)
        targets = list(filter(lambda x: os.path.splitext(x)[-1] in doc_extensions, files_in_datapath))
        if len(targets) > 0:
            target_paths = [os.path.join(self.path_data, x) for x in targets]
            for filepath in target_paths:
                os.remove(filepath)
            print(f'Removed {len(target_paths)} document files')

    @staticmethod
    def requestWithParameters(url: str, params: dict) -> requests.Response:
        response = requests.get(url, params=params)
        message = f'[status]:{response.status_code} '
        message += f'[elapsed]:{response.elapsed.microseconds}us '
        message += f'[url]:{response.request.url}'
        print(message)
        return response

    def requestAndGetContent(self, url: str, **kwargs) -> bytes:
        params = self.makeRequestParameter(**kwargs)
        resp = self.requestWithParameters(url, params)
        return resp.content

    def requestAndGetJson(self, url: str, **kwargs) -> dict:
        params = self.makeRequestParameter(**kwargs)
        resp = self.requestWithParameters(url, params)
        return resp.json()

    def setReadyForCorporationDataFramePickleFile(self, reload: bool = False):
        if os.path.isfile(self.path_corp_df_pkl):
            if reload:
                os.remove(self.path_corp_df_pkl)
            else:
                moditime = time.ctime(os.path.getmtime(self.path_corp_df_pkl))
                modidate = datetime.datetime.strptime(moditime, "%a %b %d %H:%M:%S %Y")
                now = datetime.datetime.now()
                delta = now - modidate
                if delta.days > 0:
                    os.remove(self.path_corp_df_pkl)

    def tryLoadingCorporationDataFrameFromPickleFile(self) -> bool:
        result = False
        if os.path.isfile(self.path_corp_df_pkl):
            try:
                with open(self.path_corp_df_pkl, 'rb') as fp:
                    self.df_corplist = pickle.load(fp)
                    result = True
            except Exception:
                pass
        return result

    def makeCorporationDataFrameFromXml(self, removeXmlFile: bool = True):
        xmlpath = os.path.join(self.path_data, 'CORPCODE.xml')
        tree = ET.parse(xmlpath)
        root = tree.getroot()
        tags_list = root.findall('list')  # convert all <list> tag child to dict object
        tags_list_dict = [convertTagToDict(x) for x in tags_list]
        self.df_corplist = pd.DataFrame(tags_list_dict)
        # change 'modify_date' type (str -> datetime)
        self.df_corplist['modify_date'] = pd.to_datetime(self.df_corplist['modify_date'], format='%Y%m%d')
        if removeXmlFile:
            os.remove(xmlpath)

    def serializeCorporationDataFrame(self):
        with open(self.path_corp_df_pkl, 'wb') as fp:
            pickle.dump(self.df_corplist, fp)

    def getCorporationDataFrame(self, reload: bool = False) -> pd.DataFrame:
        """
        DART에 등록된 공시대상회사 데이터프레임 반환
        고유번호(corp_code, str), 정식회사명칭(corp_name, str),
        주식의 종목코드(stock_code, str), 기업개황정보 최종변경일자(modify_date, datetime)

        :param reload: 1일단위 최신 여부와 관계없이 강제로 다시 불러오기 플래그
        :return: pandas DataFrame
        """
        self.setReadyForCorporationDataFramePickleFile(reload)
        if not self.tryLoadingCorporationDataFrameFromPickleFile():
            self.requestAndExtractZipFile("https://opendart.fss.or.kr/api/corpCode.xml")
            self.tryLoadingCorporationDataFrameFromPickleFile()
            self.makeCorporationDataFrameFromXml()
            self.serializeCorporationDataFrame()
        return self.df_corplist

    def downloadDocumentXmlFile(self, document_no: str, reload: bool = False):
        params = {'rcept_no': document_no}
        if reload:
            self.removeDocumentXmlFileInLocal(document_no)
        if not self.isDocumentXmlFileExistInLocal(document_no):
            self.requestAndExtractZipFile("https://opendart.fss.or.kr/api/document.xml", **params)
            self.solveDocumentXmlFileEncodingIssue(document_no)

    def removeDocumentXmlFileInLocal(self, document_no: str):
        path_xml = os.path.join(self.path_data, f'{document_no}.xml')
        if os.path.isfile(path_xml):
            os.remove(path_xml)

    def isDocumentXmlFileExistInLocal(self, document_no: str) -> bool:
        path_xml = os.path.join(self.path_data, f'{document_no}.xml')
        return os.path.isfile(path_xml)

    def solveDocumentXmlFileEncodingIssue(self, document_no: str):
        path_xml = os.path.join(self.path_data, f'{document_no}.xml')
        if os.path.isfile(path_xml):
            regexAnnotation = re.compile(r"<주[^>]*>")

            def replaceAnnotationBracket(source: str) -> str:
                search = regexAnnotation.search(source)
                result = source
                if search is not None:
                    span = search.span()
                    result = source[:span[0]] + '&lt;' + source[span[0]+1:span[1]-1] + '&gt;' + source[span[1]:]
                return result

            with open(path_xml, 'r', encoding='euc-kr') as fp:
                doc_lines = fp.readlines()
                for replace_set in self.xml_replace_set:
                    src = replace_set[0]
                    dest = replace_set[1]
                    doc_lines = [x.replace(src, dest) for x in doc_lines]
                doc_lines = [replaceAnnotationBracket(x) for x in doc_lines]

            with open(path_xml, 'w', encoding='utf-8') as fp:
                fp.writelines(doc_lines)

    def readDocumentXmlFile(self, document_no: str, reload: bool = False) -> ET.Element:
        self.downloadDocumentXmlFile(document_no, reload)
        path_xml = os.path.join(self.path_data, f'{document_no}.xml')
        tree = ET.parse(path_xml)
        root = tree.getroot()
        return root

    def convertDocumentXmlFileToHtml(self, document_no: str, reload: bool = False):
        xml_root = self.readDocumentXmlFile(document_no, reload)
        tag_body = xml_root.find('BODY')
        html = '<!DOCTYPE html>\n'
        html += '<html>\n'
        html += '<head>\n'
        html += '<meta charset="UTF-8">\n'
        html += '</head>\n'
        html += ET.tostring(tag_body).decode(encoding='utf-8')
        path_html = os.path.join(self.path_data, f'{document_no}.html')
        with open(path_html, 'w') as fp:
            fp.write(html)

    def searchDocument(
            self,
            corpCode: str = None,
            dateEnd: datetime.date = datetime.datetime.now().date(),
            dateBegin: datetime.date = None,
            onlyLastReport: bool = True,
            pageNumber: int = 1,
            pageCount: int = 100,
            pbType: str = None,
            pbTypeDetail: str = None,
            recursive: bool = False
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
        :param pageCount: 페이지당 건수, 기본값 = 100
        :param pbType: 공시유형 (define -> dict_pblntf_ty 참고)
        :param pbTypeDetail: 공시유형 (define -> dict_pblntf_detail_ty 참고)
        :param recursive: 메서드 내부에서의 재귀적 호출인지 여부
        :return: pandas DataFrame
            corp_code: 공시대상회사의 고유번호(8자리)
            corp_name: 공시대상회사의 종목명(상장사) 또는 법인명(기타법인)
            stock_code: 상장회사의 종목코드(6자리)
            corp_cls: 법인구분 -> Y(유가), K(코스닥), N(코넥스), E(기타)
            report_nm: 보고서명 (공시구분+보고서명+기타정보)
            rcept_no: 접수번호(14자리)
            flr_nm: 공시 제출인명
            rcept_dt: 공시 접수일자(YYYYMMDD)
            rm: 비고 (define -> dict_rm 참고)
        """
        params = {'end_de': dateEnd.strftime('%Y%m%d')}
        if corpCode is not None:
            params['corp_code'] = corpCode
        if dateBegin is not None:
            params['bgn_de'] = dateBegin.strftime('%Y%m%d')
        else:
            params['bgn_de'] = (dateEnd - datetime.timedelta(days=7)).strftime('%Y%m%d')
        params['last_reprt_at'] = 'Y' if onlyLastReport else 'N'
        params['page_no'] = max(1, pageNumber)
        params['page_count'] = max(1, min(100, pageCount))
        if pbType is not None:
            params['pblntf_ty'] = pbType
        if pbTypeDetail is not None:
            params['pblntf_detail_ty'] = pbTypeDetail
        # params['corp_cls']

        json = self.requestAndGetJson("https://opendart.fss.or.kr/api/list.json", **params)
        status = json.get('status')
        message = json.get('message')
        page_no = json.get('page_no')
        total_page = json.get('total_page')
        print(f'>> {message}({status})')
        if status != '000':
            raise Exception(message)
        data_list = json.get('list')
        df_result = pd.DataFrame(data_list)
        if not recursive:  # loop query more than 1 page - recursive call
            for page in range(page_no + 1, total_page + 1):
                df_new = self.searchDocument(
                    corpCode,
                    dateEnd,
                    dateBegin,
                    onlyLastReport,
                    page,
                    pageCount,
                    pbType,
                    pbTypeDetail,
                    recursive=True
                )
                df_result = df_result.append(df_new)
        return df_result
