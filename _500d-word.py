# -*-coding:utf-8-*-
import datetime
import json
import os
import threading
import time
import traceback
from queue import Queue

import requests
from lxml import etree
from pip._vendor.retrying import retry


class _500d_word:
    count = 0  # 简单技术用

    def __init__(self, page, order, savedir):
        self.page = page
        self.order = order
        self.save_dir = savedir

        """"""
        self.url_pattern = "http://www.500d.me/template/find/?page={}&order={}".format(self.page, self.order)
        # http://www.500d.me/order/check_product_downtimes/?pid=924&_=1552465843500
        self.detail_url_pattern = "http://www.500d.me/order/check_product_downtimes/?pid={}&_={}"
        self.headers = {
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Accept-Encoding": "gzip, deflate, sdch",
            "Accept-Language": "zh-CN,zh;q=0.8",
            "Connection": "keep-alive",
            "Cookie": "token=bba31794-515c-48c6-8edc-f2ce817a14de; MEIQIA_EXTRA_TRACK_ID=1IO6vFTaCAwJFPs0pJyesapKOgH; memberId=5393182; memberHead=http%3A%2F%2Fthirdwx.qlogo.cn%2Fmmopen%2Fvi_32%2F5CiaoDhIopQl9QA0eJs3nEWg086Xh6crVTt4wUhpsvzhHDUI30wHcDaGSuNqCEX1m1GVoKANaKicvKKtdY142pBw%2F132; memberIsBindWeixin=false; memberSafeKey=01d961b6a5f4b2ef2c89ae14a782115b; memberSign=b034c56b4543e2cb1224c2868c37fdef; memberName=wuyanzu; memberVip=%E7%BB%88%E8%BA%AB%E4%BC%9A%E5%91%98; memberRegisterDate=20181026; SESSION=62ddd816-26d9-49c3-911f-147dc909a675; MEIQIA_VISIT_ID=1IO6vAZ224IeBzgRPhXOzAEHfGI; _ga=GA1.2.90352549.1552457412; _gid=GA1.2.572284313.1552457412; Hm_lvt_f2a5f48af9d935f4001ca4c8850ce7c0=1552457412,1552459004; Hm_lpvt_f2a5f48af9d935f4001ca4c8850ce7c0=1552459133; Hm_lvt_3e432021fa3cef1b8b58965a002fd8c9=1552457413,1552459004; Hm_lpvt_3e432021fa3cef1b8b58965a002fd8c9=1552459133; Hm_lvt_e3536a6a3ab44f13b238e19790090eb5=1552457412,1552459004; Hm_lpvt_e3536a6a3ab44f13b238e19790090eb5=1552459133",
            "Host": "www.500d.me",
            "Referer": "http://www.500d.me/template/491.html",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/49.0.2623.112 Safari/537.36",
            "X-Requested-With": "XMLHttpRequest"
        }
        self.url_queue = Queue()
        self.html_queue = Queue()  # html结果
        self.list_queue = Queue()  # 列表结果
        self.data_queue = Queue()  # 最终数据,包含简历url和简历图片url

    @retry(stop_max_attempt_number=4)
    def _send_req(self, url):
        response = requests.get(url, headers=self.headers, timeout=30, verify=False)
        assert response.status_code == 200
        html = response.text
        print(html)
        print("-------------------html获取成功-------------------")
        return html

    def get_html(self):
        while True:
            url = self.url_queue.get()

            print(url)
            try:
                html = self._send_req(url)
            except Exception as e:
                traceback.print_exc()
                html = None
            # 第三次还是失败了,就存None
            self.html_queue.put(html)
            self.url_queue.task_done()  # 配合get计数减少1

    def parse_list(self):
        while True:
            html = self.html_queue.get()
            if html is not None:
                # 立马出队列
                # html_encode = html.encode()
                etree_html = etree.HTML(html)

                list = etree_html.xpath("//div[@class='inner']")
                for tr in list:
                    item = {}
                    title = tr.xpath(".//a/@title")
                    if len(title) == 0:  # 过滤第一个广告为的简历
                        continue

                    title = tr.xpath(".//a/@title")[0]
                    item["title"] = title;  # title

                    if self.isFileExist(title):
                        print("已经存在 " + title)
                        continue

                    imgUrl = tr.xpath(".//img/@src")[0]
                    item["imgUrl"] = imgUrl;  # imgUrl

                    href = tr.xpath(".//a/@href")[0]
                    print(href)
                    item["href"] = href;  # href

                    if 'template' not in href:
                        continue

                    end = href.rfind('.html')
                    start = href.rfind('/') + 1
                    id = href[start:end]
                    item["id"] = id;  # id

                    self.list_queue.put(item)
                self.html_queue.task_done()

    # 判断文件是否存在
    def isFileExist(self, title):
        names = self.file_names(self.save_dir)
        for name in names:
            if title in name:
                return True
        return False

    def file_names(self, file_dir):
        for root, dirs, files in os.walk(file_dir):
            # print(root) #当前目录路径
            # print(dirs) #当前路径下所有子目录
            # print(files) #当前路径下所有非目录子文件
            return files

    # 发起网络请求请求地址
    def parse_detail(self):
        while True:
            item = self.list_queue.get()
            print(item)

            timestamp = int(time.time());
            id_ = item['id']
            detail_url = self.detail_url_pattern.format(id_, timestamp)

            print("detail_url:" + detail_url)
            response = requests.get(detail_url, headers=self.headers)
            if (response.status_code == 200):
                course_detail_content = response.content.decode()
                data = json.loads(course_detail_content)
                type_ = data['type']
                if 'error' == type_:
                    print("zip地址解析失败,今天下载次数已经用完")
                    self.list_queue.task_done()
                    continue

                zipUrl = data['content']
                item['zipUrl'] = zipUrl
                print(item)
            else:
                print("detail 失败:" + str(response.status_code))

            self.data_queue.put(item)
            self.list_queue.task_done()

    def save_data(self):

        while True:
            item = self.data_queue.get()
            print(item)

            # 计数统计
            self.count += 1

            zipUrl = item['zipUrl']
            title = item['title']
            imgUrl = item['imgUrl']

            ############################图片下载################################
            # 这是一个图片的url
            print("开始下载 img" + " " + imgUrl)
            response = requests.get(imgUrl)
            # 获取的文本实际上是图片的二进制文本
            img = response.content
            # 下载图片
            with open(self.save_dir + title + ".png", 'wb') as f:
                f.write(img)

            ############################zip下载################################
            print("开始下载 zip" + " " + zipUrl)
            reponse = requests.get(zipUrl)
            with open(self.save_dir + title + ".zip", "wb") as code:
                code.write(reponse.content)

            self.data_queue.task_done()

    def get_url_list(self):
        self.url_queue.put(self.url_pattern)

    def run(self):
        print("--------500丁简历下载 多线程版 begin--------")
        thread_list = []

        # 1.准备url
        for i in range(1):
            t_url = threading.Thread(target=self.get_url_list)
            thread_list.append(t_url)

        # 2遍历，发送请求，获取响应
        for i in range(1):
            t_get_html = threading.Thread(target=self.get_html)
            thread_list.append(t_get_html)

        #  3.提取列表
        for i in range(1):
            t_parse_list = threading.Thread(target=self.parse_list)
            thread_list.append(t_parse_list)

        # 4.解析详情
        for i in range(10):  # content_queue里面有几十个task
            t_parse_detail = threading.Thread(target=self.parse_detail)
            thread_list.append(t_parse_detail)

        # 5.保存
        for i in range(10):
            t_save_data = threading.Thread(target=self.save_data)
            thread_list.append(t_save_data)

        print("-----开启了 " + str(len(thread_list)) + " 个线程执行任务-----")
        for t in thread_list:
            t.setDaemon(True)  # 设置守护线程，说明该线程不重要，主线程结束，子线程结束
            t.start()  # 线程启动
        for q in [self.url_queue, self.html_queue, self.list_queue,
                  self.data_queue]:
            q.join()  # 等待，让主线程等待，队列计数为0之后才会结束，否则会一直等待

        print("--------一共获取{}份简历--------".format(self.count))

    # 过滤字符串
    def filterString(self, str):
        str = str.replace("\r", "")
        str = str.replace("\n", "")
        str = str.replace("\t", "")
        str = str.replace(" ", "")
        return str


if __name__ == '__main__':
    starttime = datetime.datetime.now()
    # sort  热门推荐
    # timed 最新
    # salesd 销量
    # popular 人气

    order = "popular"  # 需要的类型
    pageStart = 1  # 开始页数
    pageEnd = 3  # 结束页数

    for page in range(pageStart, pageEnd):
        savedir = "D:\\0五百丁\\" + order + "-" + str(page) + "\\"
        if os.path.exists(savedir) is False:
            os.makedirs(savedir)

        ding = _500d_word(page, order, savedir)
        ding.run()

    # 结束时间
    endtime = datetime.datetime.now()
    print("程序耗时： ", endtime - starttime)
