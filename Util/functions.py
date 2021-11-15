import os
import _io
import xml.etree.ElementTree as ET
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QAction


def ensurePathIsExist(path: str):
    targetpath = os.path.abspath(path)
    if not os.path.isdir(targetpath):
        if os.name == 'nt':
            pathsplit = targetpath.split('\\')
            ptemp = str(pathsplit[0]) + '\\'
        else:
            pathsplit = targetpath.split('/')
            ptemp = str(pathsplit[0]) + '/'
        for i in range(len(pathsplit) - 1):
            p = pathsplit[i + 1]
            ptemp = os.path.join(ptemp, p)
            ptemp = os.path.abspath(ptemp)
            if not os.path.isdir(ptemp):
                os.mkdir(ptemp)


def writeElementToFile(elem: ET.Element, path_dest: str = '', fp: _io.TextIOWrapper = None, level: int = 0):
    if fp is None:
        dir_name = os.path.dirname(os.path.abspath(path_dest))
        ensurePathIsExist(dir_name)
        _fp = open(path_dest, 'w', encoding='utf-8')
        _fp.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>' + '\n')
    else:
        _fp = fp
    _fp.write('\t' * level)
    _fp.write('<' + elem.tag)
    for key in elem.keys():
        _fp.write(' ' + key + '="' + elem.attrib[key] + '"')
    if len(list(elem)) > 0:
        _fp.write('>\n')
        for child in list(elem):
            writeElementToFile(child, fp=_fp, level=level+1)
        _fp.write('\t' * level)
        _fp.write('</' + elem.tag + '>\n')
    else:
        if elem.text is not None:
            txt = elem.text
            txt = txt.replace('\r', '')
            txt = txt.replace('\n', '')
            txt = txt.replace('\t', '')
            if len(txt) > 0:
                _fp.write('>' + txt + '</' + elem.tag + '>\n')
            else:
                _fp.write('/>\n')
        else:
            _fp.write('/>\n')
    if level == 0:
        _fp.close()


def makeQAction(**kwargs):
    parent = None
    text = None
    iconPath = None
    triggered = None
    checkable = False
    checked = False
    enabled = True

    if 'parent' in kwargs.keys():
        parent = kwargs['parent']
    if 'text' in kwargs.keys():
        text = kwargs['text']
    if 'iconPath' in kwargs.keys():
        iconPath = kwargs['iconPath']
    if 'triggered' in kwargs.keys():
        triggered = kwargs['triggered']
    if 'checkable' in kwargs.keys():
        checkable = kwargs['checkable']
    if 'checked' in kwargs.keys():
        checked = kwargs['checked']
    if 'enabled' in kwargs.keys():
        enabled = kwargs['enabled']

    action = QAction(parent)
    action.setText(text)
    action.setIcon(QIcon(iconPath))
    if triggered is not None:
        action.triggered.connect(triggered)
    action.setCheckable(checkable)
    action.setChecked(checked)
    action.setEnabled(enabled)

    return action
