# BY @burpheart
# https://www.yuque.com/burpheart/phpaudit
# https://github.com/burpheart
import asyncio
import concurrent
import queue
import sys
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor

import requests
import json
import re
import os
import urllib.parse

tset = []


def get_session():
    session = requests.session()
    with open('cookie.txt', 'r') as f:
        content = f.read()
        result = content.split(';')
        for pair in result:
            key, value = pair.split('=', 1)
            session.cookies.set(key, value)
    return session


def remove_anchor_tags(text):
    pattern = r'<a name="[a-zA-Z0-9]*"></a>'
    cleaned_text = re.sub(pattern, '', text)
    return cleaned_text

def save_page(task):
    session = get_session()
    docsdata = session.get(
        'https://www.yuque.com/api/docs/' + task['sulg'] + '?book_id=' + task['book_id'] + '&merge_dynamic_data=false&mode=markdown')
    if (docsdata.status_code != 200):
        print("文档下载失败 页面可能被删除 ", task['book_id'] , task['sulg'], docsdata.content)
        return
    docsjson = json.loads(docsdata.content)

    f = open(task['path'], 'w', encoding='utf-8')
    print(task['path'])
    text = docsjson['data']['sourcecode']
    f.write(remove_anchor_tags(text))
    f.close()


def get_book(url="https://www.yuque.com/burpheart/phpaudit"):
    session = get_session()
    with open('cookie.txt', 'r') as f:
        for line in f:
            name, value = line.strip().split('=', 1)
            session.cookies.set(name, value)

    docsdata = session.get(url)
    data = re.findall(r"decodeURIComponent\(\"(.+)\"\)\);", docsdata.content.decode('utf-8'))
    docsjson = json.loads(urllib.parse.unquote(data[0]))
    list = {}
    temp = {}
    md = ""
    table = str.maketrans('\/:*?"<>|' + "\n\r", "___________")
    prename = ""
    if (os.path.exists("download/" + str(docsjson['book']['id'])) == False):
        os.makedirs("download/" + str(docsjson['book']['id']))

    task_queue = queue.Queue(maxsize=1024)

    for doc in docsjson['book']['toc']:
        if (doc['type'] == 'TITLE' or doc['child_uuid'] != ''):
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

                task_queue.put({
                    'book_id': str(docsjson['book']['id']),
                    'sulg': doc['url'],
                    'path': "download/" + str(docsjson['book']['id']) + '/' + temp[doc['parent_uuid']] + "/" + doc[
                        'title'].translate(table) + '.md'
                })
                # save_page(str(docsjson['book']['id']), doc['url'],
                #           "download/" + str(docsjson['book']['id']) + '/' + temp[doc['parent_uuid']] + "/" + doc[
                #               'title'].translate(table) + '.md')
            else:
                md += " " + "* [" + doc['title'] + "](" + urllib.parse.quote(
                    doc['title'].translate(table) + '.md') + ")" + "\n"
                task_queue.put({
                    'book_id': str(docsjson['book']['id']),
                    'sulg': doc['url'],
                    'path': "download/" + str(docsjson['book']['id']) + "/" + doc[
                        'title'].translate(table) + '.md'
                })
                # save_page(str(docsjson['book']['id']), doc['url'],
                #           "download/" + str(docsjson['book']['id']) + "/" + doc[
                #               'title'].translate(table) + '.md')
    f = open("download/" + str(docsjson['book']['id']) + '/' + "/SUMMARY.md", 'w', encoding='utf-8')
    f.write(md)
    f.close()

    save_page_from_queue(task_queue)


def save_page_from_queue(task_queue):
    futures = set()
    """
      从队列中读取任务并使用固定大小的线程池执行，如果线程池满则等待。

      :param task_queue: 任务队列
      :param max_workers: 线程池最大工作线程数
      """

    with concurrent.futures.ThreadPoolExecutor(task_queue.qsize()) as executor:
        while not task_queue.empty():
            task = task_queue.get()
            future = executor.submit(save_page, task)
            futures.add(future)
    completed, _ = concurrent.futures.wait(futures)

if __name__ == '__main__':
    if len(sys.argv) > 1:
        get_book(sys.argv[1])
    else:
        get_book()
