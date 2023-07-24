# BY @burpheart
# https://www.yuque.com/burpheart/phpaudit
# https://github.com/burpheart
import sys

import requests
import json
import re
import os
import urllib.parse

tset = []


def save_page(book_id, sulg, path):
    docsdata = requests.get(
        'https://www.yuque.com/api/docs/' + sulg + '?book_id=' + book_id + '&merge_dynamic_data=false&mode=markdown')
    if (docsdata.status_code != 200):
        print("文档下载失败 页面可能被删除 ", book_id, sulg, docsdata.content)
        return
    docsjson = json.loads(docsdata.content)

    f = open(path, 'w', encoding='utf-8')
    f.write(docsjson['data']['sourcecode'])
    f.close()


def get_book(url="https://www.yuque.com/burpheart/phpaudit"):
    docsdata = requests.get(url)
    data = re.findall(r"decodeURIComponent\(\"(.+)\"\)\);", docsdata.content.decode('utf-8'))
    docsjson = json.loads(urllib.parse.unquote(data[0]))
    test = []
    list = {}
    temp = {}
    md = ""
    table = str.maketrans('\/:*?"<>|' + "\n\r", "___________")
    prename = ""
    if (os.path.exists("download/" + str(docsjson['book']['id'])) == False):
        os.makedirs("download/" + str(docsjson['book']['id']))

    for doc in docsjson['book']['toc']:
        if (doc['type'] == 'TITLE' or doc['child_uuid']!= ''):
            filename = ''
            list[doc['uuid']] = {'0': doc['title'], '1': doc['parent_uuid']}
            uuid = doc['uuid']
            temp[doc['uuid']] = ''
            while True:
                if (list[uuid]['1'] != ''):
                    if temp[doc['uuid']] == '':
                        temp[doc['uuid']] = doc['title'].translate(table)
                    else:
                        temp[doc['uuid']] = list[uuid]['0'].translate(table) + '/' + temp[doc['uuid']]
                    uuid = list[uuid]['1']
                else:
                    temp[doc['uuid']] = list[uuid]['0'].translate(table) + '/' + temp[doc['uuid']]
                    break
            if ((os.path.exists("download/" + str(docsjson['book']['id']) + '/' + temp[doc['uuid']])) == False):
                os.makedirs("download/" + str(docsjson['book']['id']) + '/' + temp[doc['uuid']])
            if (temp[doc['uuid']].endswith("/")):
                md += "## " + temp[doc['uuid']][:-1] + "\n"
            else:
                md += "  " * (temp[doc['uuid']].count("/") - 1) + "* " + temp[doc['uuid']][
                                                                         temp[doc['uuid']].rfind("/") + 1:] + "\n"
        if (doc['url'] != ''):
            if doc['parent_uuid'] != "":
                if (temp[doc['parent_uuid']].endswith("/")):
                    md += " " * temp[doc['parent_uuid']].count("/") + "* [" + doc['title'] + "](" + urllib.parse.quote(
                        temp[doc['parent_uuid']] + "/" + doc['title'].translate(table) + '.md') + ")" + "\n"
                else:
                    md += "  " * temp[doc['parent_uuid']].count("/") + "* [" + doc['title'] + "](" + urllib.parse.quote(
                        temp[doc['parent_uuid']] + "/" + doc['title'].translate(table) + '.md') + ")" + "\n"
                save_page(str(docsjson['book']['id']), doc['url'],
                          "download/" + str(docsjson['book']['id']) + '/' + temp[doc['parent_uuid']] + "/" + doc[
                              'title'].translate(table) + '.md')
            else:
                md += " " + "* [" + doc['title'] + "](" + urllib.parse.quote(
                    doc['title'].translate(table) + '.md') + ")" + "\n"
                save_page(str(docsjson['book']['id']), doc['url'],
                          "download/" + str(docsjson['book']['id']) + "/" + doc[
                              'title'].translate(table) + '.md')
    f = open("download/" + str(docsjson['book']['id']) + '/' + "/SUMMARY.md", 'w', encoding='utf-8')
    f.write(md)
    f.close()


if __name__ == '__main__':
    if len(sys.argv) > 1:
        get_book(sys.argv[1])
    else:
        get_book()
