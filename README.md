# OPENDART-Python
![opendart](./Resource/opendart_logo.png)<br>
금융감독원 전자공시시스템(DART) 오픈API 서비스 인터페이스 ([OPENDART](http://opendart.fss.or.kr))

Language
--
Python (tested in version 3.8)

Requirements
--
```
lxml
pandas
requests
PyQt5
requests-HTML
```

Manual
--

Notice
--
If you have a problem of encoding after html rendering, you sholuld modify render functions in source code 
**requests-html.py** like beneath.<br>
You can find source code script file in "{$Python Path}/Lib/site-packages".
```python
class HTML(BaseParser):
    def render(self, retries: int = 8, script: str = None, wait: float = 0.2, scrolldown=False, sleep: int = 0, reload: bool = True, timeout: Union[float, int] = 8.0, keep_page: bool = False):
        """ ... """
        # html = HTML(url=self.url, html=content.encode(DEFAULT_ENCODING), default_encoding=DEFAULT_ENCODING)
        html = HTML(url=self.url, html=content.encode(self.encoding), default_encoding=DEFAULT_ENCODING)

    async def arender(self, retries: int = 8, script: str = None, wait: float = 0.2, scrolldown=False, sleep: int = 0, reload: bool = True, timeout: Union[float, int] = 8.0, keep_page: bool = False):
        """ ... """
        # html = HTML(url=self.url, html=content.encode(DEFAULT_ENCODING), default_encoding=DEFAULT_ENCODING)
        html = HTML(url=self.url, html=content.encode(self.encoding), default_encoding=DEFAULT_ENCODING)
```