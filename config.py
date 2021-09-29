# Author: Yogyui
import os
from lxml import etree
from Util import writeElementToFile


class OpenDartConfiguration:
    path_config: str
    path_local_file: str
    api_key: str

    def __init__(self):
        curpath = os.path.dirname(os.path.abspath(__file__))
        self.path_config = os.path.join(curpath, 'Config')
        if not os.path.isdir(self.path_config):
            os.mkdir(self.path_config)
        self.path_local_file = os.path.join(self.path_config, 'opendartconfig.xml')

        self.api_key = ''
        self.doc_str_replace_list = [
            ('&cr;', '&#13;'),
            ('M&A', 'M&amp;A'),
            ('R&D', 'R&amp;D'),
            ('S&P', 'S&amp;P')
        ]
        self.mysql_params = {
            'host': '',
            'port': 3306,
            'user': '',
            'password': '',
            'databse': ''
        }

        self.loadFromLocalFile()

    @staticmethod
    def findChildNode(node: etree.Element, name: str, appendWhenNotExist: bool = False):
        child = node.find(name)
        if child is None and appendWhenNotExist:
            child = etree.Element(name)
            node.append(child)
        return child

    def loadFromLocalFile(self):
        if not os.path.isfile(self.path_local_file):
            self.saveToLocalFile()
        tree = etree.parse(self.path_local_file)
        root = tree.getroot()

        node = self.findChildNode(root, 'api_key')
        self.api_key = node.text
        if self.api_key is None:
            self.api_key = ''

        node = self.findChildNode(root, 'mysql')
        if node is not None:
            for key in self.mysql_params.keys():
                child = self.findChildNode(node, key)
                if child is not None:
                    text = child.text if child.text is not None else ''
                    if key == 'port':
                        try:
                            self.mysql_params[key] = int(text)
                        except ValueError:
                            self.mysql_params[key] = 3306
                    else:
                        self.mysql_params[key] = text

    def saveToLocalFile(self):
        if os.path.isfile(self.path_local_file):
            tree = etree.parse(self.path_local_file)
        else:
            tree = etree.ElementTree(etree.Element('OpenDartConfig'))
        root = tree.getroot()

        node = self.findChildNode(root, 'api_key', True)
        node.text = self.api_key

        node = self.findChildNode(root, 'mysql', True)
        for key, value in self.mysql_params.items():
            child_node = self.findChildNode(node, key, True)
            child_node.text = str(value)

        writeElementToFile(root, self.path_local_file)
