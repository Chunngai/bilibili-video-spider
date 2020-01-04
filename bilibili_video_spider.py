#!/usr/bin/python3
# -*- coding: utf-8 -*-

import queue
import threading
import json
import argparse

import requests
from bs4 import BeautifulSoup


def validate_from_to_p_num(root_url, headers, from_p_num, to_p_num):
    # checks if from index < to_p_num
    if not from_p_num <= to_p_num:
        print("bilibili-video-spider: error: FROM-P-NUM greater than to_p_num")
        exit(1)

    # checks if the p num is out of range
    try:
        r = requests.get(root_url, headers=headers)
        html_text = r.text
    except:
        print("bilibili-video-spider.py: error: cannot access to {}".format(root_url))
        exit(2)
    else:
        soup = BeautifulSoup(html_text, "html.parser")

        # finds the ul tag whose class is list-box
        ul_list_box = soup.find("ul", "list-box")

        # calculates the mex p num
        max_p_num = len(ul_list_box.find_all("li"))

        if from_p_num <= 0:
            print("bilibili-video-spider.py: error: FROM-P-NUM should be greater than 0")
            exit(3)

        if to_p_num > max_p_num:
            print("bilibili-video-spider.py: error: the greatest TO-P-NUM: {}".format(max_p_num))
            exit(4)


def create_queues(from_p_num, to_p_num):
    # creates a queue for storing p numbers
    p_num_queue = queue.Queue()
    # put p numbers into the queue
    for p_num in range(from_p_num, to_p_num + 1):
        p_num_queue.put(p_num)

    # creates a queue for storing (audio url, video url) of each video
    url_queue = queue.Queue()

    return p_num_queue, url_queue


class GetUrlThread(threading.Thread):
    def __init__(self, name, root_url, headers, p_num_queue, url_queue):
        super(GetUrlThread, self).__init__()
        self.name = name
        self.root_url = root_url
        self.headers = headers
        self.p_num_queue = p_num_queue
        self.url_queue = url_queue

        self.url = ""
        self.p_num = 0
        self.html_text = ""
        self.audio_url = ""
        self.video_url = ""

    def run(self):
        while not self.p_num_queue.empty():
            # gets a p num
            self.p_num = self.p_num_queue.get()

            # generates the url of the p
            self.url = self.root_url + "?p=" + str(self.p_num)

            # gets the html text
            self.get_html_text()

            # gets (audio, video (without sound) url)
            self.get_audio_video_url()

            # puts (audio, video (without sound) url) into the url queue
            self.url_queue.put((self.p_num, self.audio_url, self.video_url))

    def get_html_text(self):
        # # makes a headless chrome driver
        # chrome_options = Options()
        # chrome_options.add_argument("--headless")
        # driver = webdriver.Chrome(options=chrome_options)
        #
        # # accesses the url
        # driver.get(self.url)
        #
        # try:
        #     # waits til the script containing "window.__playinfo__"
        #     WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.XPATH, "/html/head/script[3]")))
        #     self.html_text = driver.page_source
        # except:
        #     print("bilibili_video_spider.py: error: cannot get html text of p {}".format(self.p_num))
        try:
            r = requests.get(self.url, headers=self.headers)
            self.html_text = r.text
        except:
            print("bilibili_video_spider.py: error: cannot get html text of p {}".format(self.p_num))

    def get_audio_video_url(self):
        soup = BeautifulSoup(self.html_text, "html.parser")

        script_list = soup.find_all("script")
        script_window_playinfo = ""
        for script in script_list:
            try:
                if "window.__playinfo__" in script.string:
                    script_window_playinfo = script.string[20:]
            except:
                pass

        if not script_window_playinfo:
            print("bilibili_video_spider.py: error: cannot get <script> with needed urls for p{}".format(self.p_num))

        # gets audio url and video (without sound) url
        playinfo_dict = json.loads(script_window_playinfo)

        self.video_url = playinfo_dict["data"]["dash"]["video"][0]["baseUrl"]
        self.audio_url = playinfo_dict["data"]["dash"]["audio"][0]["baseUrl"]


class DownloadThread(threading.Thread):
    def __init__(self, name, root_url, av_num, headers, url_queue):
        super(DownloadThread, self).__init__()
        self.name = name
        self.root_url = root_url
        self.av_num = av_num
        self.headers = headers
        self.url_queue = url_queue

        self.p_num = 0
        self.audio_url = ""
        self.video_url = ""

    def run(self):
        while True:
            try:
                # gets a (audio url, video (without sound) url)
                self.p_num, self.audio_url, self.video_url = self.url_queue.get(block=True, timeout=5)

                # downloads the audio and the video
                self.download_audio_n_video()
            except:
                break

    def download_audio_n_video(self):
        headers = {
            'Referer': self.root_url,
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 '
                          'Safari/537.36'
        }

        try:
            print("downloading audio and video (without sound) in p{}".format(self.p_num))

            r_audio = requests.get(self.audio_url, headers=headers)
            r_video = requests.get(self.video_url, headers=headers)
        except:
            print("bilibili_video_spider.py: error: cannot download data in p{}".format(self.p_num))
        else:
            print("saving audio and video (without sound) in p{}".format(self.p_num))

            with open("av_{}_p_{}_audio.m4s".format(self.av_num, self.p_num), "wb") as f_audio:
                f_audio.write(r_audio.content)

            with open("av_{}_p_{}_video.m4s".format(self.av_num, self.p_num), "wb") as f_video:
                f_video.write(r_video.content)


def create_threads(root_url, av_num, headers, p_num_queue, url_queue):
    get_url_thread_list = []
    # threads for storing (audio url, video (without sound) url)
    for i in range(6):
        get_url_thread = GetUrlThread("get url thread {}".format(i + 1), root_url, headers, p_num_queue, url_queue)
        get_url_thread_list.append(get_url_thread)

    download_url_thread_list = []
    # threads for downloading (audio url, video (without sound) url)
    for i in range(6):
        download_url_thread = DownloadThread("download url thread {}".format(i + 1), root_url, av_num, headers,
                                             url_queue)
        download_url_thread_list.append(download_url_thread)

    return get_url_thread_list, download_url_thread_list


def start_threads(get_url_thread_list, download_url_thread_list):
    for get_url_thread in get_url_thread_list:
        get_url_thread.start()

    for download_url_thread in download_url_thread_list:
        download_url_thread.start()


def join_threads(get_url_thread_list, download_url_thread_list):
    for get_url_thread in get_url_thread_list:
        get_url_thread.join()

    for download_url_thread in download_url_thread_list:
        download_url_thread.join()


def bilibili_video_spider(av_num, from_p_num, to_p_num):
    # generates the root url
    root_url = "https://www.bilibili.com/video/av{}".format(av_num)

    # generates the headers
    headers = {
        'Referer': root_url,
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 '
                      'Safari/537.36'
    }

    # checks if the from index and to index is valid
    validate_from_to_p_num(root_url, headers, from_p_num, to_p_num)

    print("ready to scratch videos from av {}".format(av_num))

    # creates a queue for storing p numbers,
    # and a queue for (audio url, video (without sound) url) of each p
    p_num_queue, url_queue = create_queues(from_p_num, to_p_num)

    # creates a thread for retrieving (audio url, video (without sound) url) of each p,
    # and a thread for downloading (audio url, video (without sound) url) and merging them into a video with sound
    get_url_thread_list, download_thread_list = create_threads(root_url, av_num, headers, p_num_queue, url_queue)

    # starts the threads, respectively
    start_threads(get_url_thread_list, download_thread_list)

    # joins the threads, respectively
    join_threads(get_url_thread_list, download_thread_list)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="bilibili_video_spider.py - a tool for scratching videos from bilibili")

    parser.add_argument("--av-num", "-a", action="store", required=True, type=int,
                        help="av num of the video to be scratched")
    parser.add_argument("--from-p-num", "-f", action="store", required=True, type=int,
                        help="p number from which videos are to be scratched")
    parser.add_argument("--to-p-num", "-t", action="store", required=True, type=int,
                        help="p number to which videos are to be scratched")

    args = parser.parse_args()

    bilibili_video_spider(args.av_num, args.from_p_num, args.to_p_num)
