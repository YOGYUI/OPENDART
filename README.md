# OPENDART-Python
![opendart](./Resource/opendart_logo.png)<br>
Interface for Open-API service which is provided by DART(Data Analysis, Retrieval and Transfer) system of Financial Supervisory Service(FSS) (Republic of Korea) 
([OPENDART](http://opendart.fss.or.kr))

Language
--
Python (Developed and test with version 3.8.5)

Package Requirements
--
```
lxml>=4.6.0
PyQt5>=5.15.0
pandas>=1.3.0
pymysql>=1.0.0
requests>=2.26.0
requests-HTML>=0.10.0
PyQtWebEngine<=5.15.3
python-dateutil>=2.8.0
```

Manual
--
Basic use example
```python
from opendart import *
import pandas as pd

dart_api_key = "Your api key from open-dart"
dart = OpenDart()
dart.setApiKey(dart_api_key)
df_comp_info: pd.DataFrame = dart.getCompanyInformation('00126380')  # 삼성전자 기업개황
```
You can get OPENDART API key from [OPENDART](http://opendart.fss.or.kr) web page.<br>
Detailed descriptions of all methods are written in source code([opendart.py](https://github.com/YOGYUI/OPENDART/tree/main/opendart.py)) as comments.

### Graphical User Interface (GUI)
Developed GUI using PyQt5 (Multi Docement Interface).<br>
Various OPENDART API can be accessed by user-friendly sub windows.
<br>
####Basic use example
```python
from opendart import *
from GUI import *
from PyQt5.QtWidgets import *

app = QApplication(sys.argv)
dart = OpenDart()
wnd = MainWindow(dart)
wnd.show()
app.exec_()
```
#### Screenshot


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
Replacing can be done with [script](https://github.com/YOGYUI/OPENDART/tree/main/Util/requests_html_modify_source.py) in repository.
