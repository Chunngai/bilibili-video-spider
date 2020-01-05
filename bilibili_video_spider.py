#!/usr/bin/python3
# -*- coding: utf-8 -*-

import queue
import threading
import json
import argparse
import os
import time
import base64

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


def get_info(root_url, headers):
    try:
        r = requests.get(root_url, headers=headers)
        html_text = r.text
    except:
        print("bilibili-video-spider.py: error: cannot access to {}".format(root_url))
        exit(1)
    else:
        soup = BeautifulSoup(html_text, "html.parser")

        # gets the title of the videos
        title = soup.find("h1", "video-title")["title"]

        # finds the ul tag whose class is list-box
        ul_list_box = soup.find("ul", "list-box")
        # calculates the p num
        p_num = len(ul_list_box.find_all("li"))

        # checks if the videos are m4s or flv
        if "m4s?" in html_text:
            ext = "m4s"
        else:
            ext = "flv"

        return title, p_num, ext


def log_in():
    login_page_url = "https://passport.bilibili.com/login"  # log in page

    # generates a headless chrome driver
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    driver = webdriver.Chrome(options=chrome_options)

    print("getting qr code for logging in")

    # accesses the log in page
    driver.get(login_page_url)
    time.sleep(2)

    login_html_text = driver.page_source

    # gets qr code
    login_soup = BeautifulSoup(login_html_text, "html.parser")

    try:
        div_qrcode_img = login_soup.find("div", "qrcode-img")
        qrcode_img_url = div_qrcode_img.img["src"].split(',')[1:][0]
    except:
        print("bilibili-video-spider.py: error: cannot log in when scratching flv videos")
    else:
        # gets and saves the qr code for logging in
        qrcode_img = base64.urlsafe_b64decode(qrcode_img_url + '=' * (4 - len(qrcode_img_url) % 4))
        with open("qrcode.png", "wb") as f:
            f.write(qrcode_img)

    # displays the qr code
    print("scan the qr code for logging in")
    print("flv videos can also be scratched without logging in, but with lower quality")
    print("close the qr code after scanning")

    qrcode_img = mpimg.imread("qrcode.png")
    plt.imshow(qrcode_img)
    plt.axis(False)
    plt.show()

    # removes the qr code
    os.remove("qrcode.png")

    return driver


def make_dir(root_dir, title):
    dir_path = os.path.join(root_dir, title)

    try:
        os.mkdir(dir_path)
    except FileExistsError:
        print("bilibili-video-spider: error: {} already exists".format(dir_path))

    return dir_path


def validate_from_to_p_num(from_p_num, to_p_num, p_num):
    # checks if from index < to_p_num
    if not from_p_num <= to_p_num:
        print("bilibili-video-spider: error: FROM-P-NUM greater than to_p_num")
        exit(2)

    # checks if the p num is out of range
    if from_p_num <= 0:
        print("bilibili-video-spider.py: error: FROM-P-NUM should be greater than 0")
        exit(3)

    if to_p_num > p_num:
        print("bilibili-video-spider.py: error: the greatest TO-P-NUM: {}".format(p_num))
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
    def __init__(self, name, root_url, headers, driver, p_num_queue, url_queue):
        super(GetUrlThread, self).__init__()
        self.name = name
        self.root_url = root_url
        self.headers = headers
        self.driver = driver
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

            # gets (audio, video (without sound for m4s) url)
            self.get_audio_video_url()

            # puts (audio, video (without sound for m4s) url) into the url queue
            self.url_queue.put((self.p_num, self.audio_url, self.video_url))

    def get_html_text(self):
        if not self.driver:
            # for m4s videos
            try:
                r = requests.get(self.url, headers=self.headers)
                self.html_text = r.text
            except:
                print("bilibili_video_spider.py: error: cannot get html text of p {}".format(self.p_num))
        else:
            # for flv videos
            try:
                driver_lock.acquire()
                self.driver.get(self.url)

                WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.XPATH, "/html/head/script[3]")))
                self.html_text = self.driver.page_source
            except:
                print("bilibili_video_spider.py: error: cannot get html text of p {}".format(self.p_num))
            finally:
                driver_lock.release()

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

        # gets audio url and video (without sound for m4s) url
        playinfo_dict = json.loads(script_window_playinfo)

        try:
            # for m4s videos
            self.video_url = playinfo_dict["data"]["dash"]["video"][0]["baseUrl"]
            self.audio_url = playinfo_dict["data"]["dash"]["audio"][0]["baseUrl"]
        except:
            # for flv videos
            self.video_url = playinfo_dict["data"]["durl"][0]["url"]


class DownloadThread(threading.Thread):
    def __init__(self, name, root_url, title, headers, dir_path, url_queue):
        super(DownloadThread, self).__init__()
        self.name = name
        self.root_url = root_url
        self.title = title
        self.headers = headers
        self.dir_path = dir_path
        self.url_queue = url_queue

        self.p_num = 0
        self.audio_url = ""
        self.video_url = ""

    def run(self):
        while True:
            try:
                # gets a (audio url, video (without sound for m4s) url)
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
            r_m4s_audio = ""
            r_m4s_video = ""
            r_flv = ""

            if self.audio_url:
                # for m4s videos
                print("downloading audio and video (without sound) in p{}".format(self.p_num))

                r_m4s_audio = requests.get(self.audio_url, headers=headers)
                r_m4s_video = requests.get(self.video_url, headers=headers)
            else:
                # for flv videos
                print("downloading video in p{}".format(self.p_num))

                r_flv = requests.get(self.video_url, headers=headers)
        except:
            print("bilibili_video_spider.py: error: cannot download data in p{}".format(self.p_num))
        else:
            # saves the video (and the audio for m4s)
            if self.audio_url:
                # for m4s videos
                print("saving audio and video (without sound) in p{}".format(self.p_num))

                with open(os.path.join(self.dir_path, "{}_p{}_audio.m4s").format(self.title, self.p_num),
                          "wb") as f_audio:
                    f_audio.write(r_m4s_audio.content)
                with open(os.path.join(self.dir_path, "{}_p{}_video.m4s").format(self.title, self.p_num),
                          "wb") as f_video:
                    f_video.write(r_m4s_video.content)
            else:
                # for flv videos
                print("saving video in p{}".format(self.p_num))

                with open(os.path.join(self.dir_path, "{}_p{}.flv").format(self.title, self.p_num), "wb") as f:
                    f.write(r_flv.content)


def create_threads(root_url, title, headers, dir_path, driver, p_num_queue, url_queue):
    get_url_thread_list = []
    # threads for storing (audio url, video (without sound for m4s) url)
    for i in range(6):
        get_url_thread = GetUrlThread("get url thread {}".format(i + 1), root_url, headers, driver, p_num_queue, url_queue)
        get_url_thread_list.append(get_url_thread)

    download_url_thread_list = []
    # threads for downloading (audio url, video (without sound for m4s) url)
    for i in range(6):
        download_url_thread = DownloadThread("download url thread {}".format(i + 1), root_url, title, headers, dir_path,
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


def bilibili_video_spider(av_num, from_p_num, to_p_num, root_dir):
    # generates the root url
    root_url = "https://www.bilibili.com/video/av{}".format(av_num)

    # generates the headers
    headers = {
        'Referer': root_url,
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 '
                      'Safari/537.36'
    }

    # gets basic info of the video
    title, p_num, ext = get_info(root_url, headers)

    # simulates logging in if the videos are flv
    if ext == "flv":
        driver = log_in()
    else:
        driver = None

    # checks if the from index and to index is valid
    validate_from_to_p_num(from_p_num, to_p_num, p_num)

    print("ready to scratch videos from av {}".format(av_num))

    # makes a dir for storing the videos
    dir_path = make_dir(root_dir, title)

    # creates a queue for storing p numbers,
    # and a queue for (audio url, video (without sound) url) of each p
    p_num_queue, url_queue = create_queues(from_p_num, to_p_num)

    # creates a thread for retrieving (audio url, video (without sound) url) of each p,
    # and a thread for downloading (audio url, video (without sound) url) and merging them into a video with sound
    get_url_thread_list, download_thread_list = create_threads(root_url, title, headers, dir_path, driver, p_num_queue,
                                                               url_queue)

    # starts the threads, respectively
    start_threads(get_url_thread_list, download_thread_list)

    # joins the threads, respectively
    join_threads(get_url_thread_list, download_thread_list)


def validate_dir(input_dir_path):
    if not os.path.exists(input_dir_path):
        raise argparse.ArgumentTypeError("path not exists")
    if not os.path.isdir(input_dir_path):
        raise argparse.ArgumentTypeError("not a dir")

    return input_dir_path


if __name__ == '__main__':
    driver_lock = threading.Lock()

    parser = argparse.ArgumentParser(
        description="bilibili_video_spider.py - a tool for scratching videos from bilibili")

    parser.add_argument("--av-num", "-a", action="store", required=True, type=int,
                        help="av num of the video to be scratched")
    parser.add_argument("--from-p-num", "-f", action="store", required=True, type=int,
                        help="p number from which videos are to be scratched")
    parser.add_argument("--to-p-num", "-t", action="store", required=True, type=int,
                        help="p number to which videos are to be scratched")
    parser.add_argument("--dir", "-d", action="store", default=os.getcwd(), type=validate_dir,
                        help="directory for storing scratched videos")

    args = parser.parse_args()

    bilibili_video_spider(args.av_num, args.from_p_num, args.to_p_num, args.dir)
