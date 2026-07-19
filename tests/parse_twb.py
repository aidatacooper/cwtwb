import xml.etree.ElementTree as ET
import sys

file_path = r'c:\Users\imgwho\Desktop\projects\20260227-cwtwb\tests\fixtures\advent_calendar.twb'
tree = ET.parse(file_path)
root = tree.getroot()

worksheets = root.find('worksheets')
if worksheets is not None:
    for worksheet in worksheets.findall('worksheet'):
        name = worksheet.get('name')
        print(f'Worksheet: {name}')
        table = worksheet.find('table')
        if table is not None:
            view = table.find('view')
            if view is not None:
                panes_tag = view.find('panes')
                if panes_tag is not None:
                    for pane in panes_tag.findall('pane'):
                        mark = pane.find('mark')
                        if mark is not None:
                            print(f'  Mark class: {mark.get("class")}')
                            encodings = pane.findall('encodings')
                            if encodings:
                                for enc in encodings[0]:
                                    print(f'    Encoding: {enc.tag} - {enc.get("column")}')
        print('---')
