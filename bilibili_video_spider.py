#!/usr/bin/python3
# -*- coding: utf-8 -*-

import queue
import threading
import json
import argparse
import os
import time
import base64
import subprocess

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


def get_p_title_list(soup):
    # finds the script tag containing all p titles
    script_list = soup.find_all("script")

    window_initial_state = ""
    for script in script_list:
        try:
            if "window.__INITIAL_STATE__={" in script.string:
                window_initial_state = script.string[25:]
        except:
            pass

    # retrieves all p titles
    raw_page_list = json.loads(window_initial_state.split(";(function()")[0])["videoData"]["pages"]
    p_title_list = [raw_page["part"] for raw_page in raw_page_list]
    return p_title_list


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
        video_title = soup.find("h1", "video-title")["title"]

        # gets the page title list of the video
        p_title_list = get_p_title_list(soup)

        # calculates the p num
        p_num = len(p_title_list)

        # checks if the videos are m4s or flv
        if "m4s?" in html_text:
            ext = "m4s"
        else:
            ext = "flv"

        return video_title, p_title_list, p_num, ext


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


class BilibiliVideo:
    def __init__(self, av_num="", total_p_num=0, video_title="", p_title_list=None, ext=""):
        self.av_num = av_num
        self.url = ""
        self.total_p_num = total_p_num
        self.video_title = video_title
        self.p_title_list = p_title_list
        self.ext = ext

    def set_url(self):
        self.url = "https://www.bilibili.com/video/av{}".format(self.av_num)


class BilibiliVideoOneP(BilibiliVideo):
    def __init__(self, bilibili_video, p_num=0, html_text="", audio_url="", video_url="",
                 audio_content=b'', video_content=b''):
        super(BilibiliVideoOneP, self).__init__(bilibili_video.av_num, bilibili_video.total_p_num,
                                                bilibili_video.video_title, bilibili_video.p_title_list,
                                                bilibili_video.ext)
        self.url = bilibili_video.url

        self.p_num = p_num
        self.p_url = ""
        self.p_title = ""
        self.html_text = html_text
        self.audio_url = audio_url  # makes sense only for m4s videos
        self.video_url = video_url  # originally without sound for m4s videos
        self.audio_content = audio_content  # makes sense only for m4s videos
        self.video_content = video_content  # originally without sound for m4s videos

    def set_p_url(self):
        self.p_url = "{}?p={}".format(self.url, self.p_num)

    def set_p_title(self):
        self.p_title = self.p_title_list[self.p_num - 1]


class GetUrlThread(threading.Thread):
    def __init__(self, thread_name, headers, driver, bilibili_video, p_num_queue, url_queue):
        super(GetUrlThread, self).__init__()
        self.bilibili_video_one_p = BilibiliVideoOneP(bilibili_video)

        self.thread_name = thread_name
        self.headers = headers
        self.driver = driver
        self.p_num_queue = p_num_queue
        self.url_queue = url_queue

    def run(self):
        while not self.p_num_queue.empty():
            # gets a p num
            self.bilibili_video_one_p.p_num = self.p_num_queue.get()

            # generates the url of the p
            self.bilibili_video_one_p.set_p_url()

            # sets the p title
            self.bilibili_video_one_p.set_p_title()

            # gets the html text
            self.get_html_text()

            # gets (audio, video (without sound for m4s) url)
            self.get_audio_video_url()

            # puts (audio, video (without sound for m4s) url) into the url queue
            self.url_queue.put(self.bilibili_video_one_p)

    def get_html_text(self):
        if not self.driver:
            # for m4s videos
            try:
                r = requests.get(self.bilibili_video_one_p.p_url, headers=self.headers)
                self.bilibili_video_one_p.html_text = r.text
            except:
                print("bilibili_video_spider.py: error: cannot get html text of p {}".format(
                    self.bilibili_video_one_p.p_num))
        else:
            # for flv videos
            try:
                driver_lock.acquire()
                self.driver.get(self.bilibili_video_one_p.p_url)

                WebDriverWait(self.driver, 10).until(ec.presence_of_element_located((By.XPATH, "/html/head/script[3]")))
                self.bilibili_video_one_p.html_text = self.driver.page_source
            except:
                print("bilibili_video_spider.py: error: cannot get html text of p {}".format(
                    self.bilibili_video_one_p.p_num))
            finally:
                driver_lock.release()

    def get_audio_video_url(self):
        soup = BeautifulSoup(self.bilibili_video_one_p.html_text, "html.parser")

        script_list = soup.find_all("script")
        script_window_playinfo = ""
        for script in script_list:
            try:
                if "window.__playinfo__" in script.string:
                    script_window_playinfo = script.string[20:]
            except:
                pass

        if not script_window_playinfo:
            print("bilibili_video_spider.py: error: cannot get <script> with needed urls for p{}".format(
                self.bilibili_video_one_p.p_num))

        # gets audio url and video (without sound for m4s) url
        playinfo_dict = json.loads(script_window_playinfo)

        try:
            # for m4s videos
            self.bilibili_video_one_p.video_url = playinfo_dict["data"]["dash"]["video"][0]["baseUrl"]
            self.bilibili_video_one_p.audio_url = playinfo_dict["data"]["dash"]["audio"][0]["baseUrl"]
        except KeyError:
            # for flv videos
            self.bilibili_video_one_p.video_url = playinfo_dict["data"]["durl"][0]["url"]
        except:
            print(
                "bilibili_video_spider: error: cannot get download url for p{}".format(self.bilibili_video_one_p.p_num))


class DownloadThread(threading.Thread):
    def __init__(self, thread_name, headers, dir_path, url_queue):
        super(DownloadThread, self).__init__()
        self.bilibili_video_one_p = None
        self.thread_name = thread_name
        self.headers = headers
        self.dir_path = dir_path
        self.url_queue = url_queue

        self.audio_path = ""
        self.video_path = ""
        self.m4s_file_name = ""

    def run(self):
        while p_num_scratched < total_p_num_to_be_scratched:
            try:
                print(p_num_scratched, total_p_num_to_be_scratched)
                # gets a (audio url, video (without sound for m4s) url)
                self.bilibili_video_one_p = self.url_queue.get(True, timeout=10)

                # downloads the audio and the video
                self.download_audio_n_video()
            except queue.Empty:
                break

    def download_audio_n_video(self):
        try:
            if self.bilibili_video_one_p.audio_url:
                # for m4s videos
                print("downloading audio and video (without sound) in p{}".format(self.bilibili_video_one_p.p_num))

                self.bilibili_video_one_p.audio_content = requests.get(self.bilibili_video_one_p.audio_url,
                                                                       headers=self.headers).content
                self.bilibili_video_one_p.video_content = requests.get(self.bilibili_video_one_p.video_url,
                                                                       headers=self.headers).content
            else:
                # for flv videos
                print("downloading video in p{}".format(self.bilibili_video_one_p.p_num))

                self.bilibili_video_one_p.video_content = requests.get(self.bilibili_video_one_p.video_url,
                                                                       headers=self.headers).content
        except:
            print(
                "bilibili_video_spider.py: error: cannot download data in p{}".format(self.bilibili_video_one_p.p_num))
        else:
            # saves the video (and the audio for m4s)
            if self.bilibili_video_one_p.audio_url:
                # for m4s videos
                print("saving audio and video (without sound) in p{}".format(self.bilibili_video_one_p.p_num))

                self.audio_path = os.path.join(self.dir_path, "{}_p{}_audio.m4s").format(
                    self.bilibili_video_one_p.p_title,
                    self.bilibili_video_one_p.p_num)
                self.video_path = os.path.join(self.dir_path, "{}_p{}_video.m4s").format(
                    self.bilibili_video_one_p.p_title,
                    self.bilibili_video_one_p.p_num)
                self.m4s_file_name = os.path.join(self.dir_path, "p{}_{}.mp4").format(
                    self.bilibili_video_one_p.p_num, self.bilibili_video_one_p.p_title)

                with open(self.audio_path, "wb") as f_audio:
                    f_audio.write(self.bilibili_video_one_p.audio_content)
                with open(self.video_path, "wb") as f_video:
                    f_video.write(self.bilibili_video_one_p.video_content)

                self.combine()
            else:
                # for flv videos
                print("saving video in p{}".format(self.bilibili_video_one_p.p_num))

                self.video_path = os.path.join(self.dir_path, "{}_p{}.flv").format(self.bilibili_video_one_p.title,
                                                                                   self.bilibili_video_one_p.p_num)

                with open(self.video_path, "wb") as f:
                    f.write(self.bilibili_video_one_p.video_content)

            try:
                p_num_scratched_lock.acquire()

                global p_num_scratched
                p_num_scratched += 1
            finally:
                p_num_scratched_lock.release()

    def combine(self):
        # combines audio and video of the m4s file
        print("combining {} and {} into {}".format(os.path.basename(self.video_path),
                                                   os.path.basename(self.audio_path),
                                                   os.path.basename(self.m4s_file_name)))

        subprocess.call(
            ["ffmpeg -y -i {} -i {} -codec copy {} &> /dev/null".format(self.video_path, self.audio_path,
                                                                        self.m4s_file_name)],
            shell=True)

        # removes tmp m4s files
        os.remove(self.audio_path)
        os.remove(self.video_path)


def create_threads(headers, dir_path, driver, bilibili_video, p_num_queue, url_queue):
    get_url_thread_list = []
    # threads for storing (audio url, video (without sound for m4s) url)
    for i in range(6):
        get_url_thread = GetUrlThread("get url thread {}".format(i + 1), headers, driver, bilibili_video,
                                      p_num_queue,
                                      url_queue)
        get_url_thread_list.append(get_url_thread)

    download_url_thread_list = []
    # threads for downloading (audio url, video (without sound for m4s) url)
    for i in range(6):
        download_url_thread = DownloadThread("download url thread {}".format(i + 1), headers, dir_path, url_queue)
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
    bilibili_video = BilibiliVideo(av_num=av_num)

    # generates the root url
    bilibili_video.set_url()

    # generates the headers
    headers = {
        'Referer': bilibili_video.url,
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 '
                      'Safari/537.36'
    }

    # gets basic info of the video
    bilibili_video.video_title, bilibili_video.p_title_list, bilibili_video.total_p_num, bilibili_video.ext = get_info(
        bilibili_video.url, headers)

    # simulates logging in if the videos are flv
    if bilibili_video.ext == "flv":
        driver = log_in()
    else:
        driver = None

    # checks if the from index and to index is valid
    validate_from_to_p_num(from_p_num, to_p_num, bilibili_video.total_p_num)

    global total_p_num_to_be_scratched
    total_p_num_to_be_scratched = to_p_num - from_p_num + 1

    print("ready to scratch videos from av{}: {}".format(bilibili_video.av_num, bilibili_video.video_title))

    # makes a dir for storing the videos
    dir_path = make_dir(root_dir, bilibili_video.video_title)

    # creates a queue for storing p numbers,
    # and a queue for (audio url, video (without sound) url) of each p
    p_num_queue, url_queue = create_queues(from_p_num, to_p_num)

    # creates a thread for retrieving (audio url, video (without sound) url) of each p,
    # and a thread for downloading (audio url, video (without sound) url) and merging them into a video with sound
    get_url_thread_list, download_thread_list = create_threads(headers, dir_path, driver, bilibili_video, p_num_queue,
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
    p_num_scratched_lock = threading.Lock()
    total_p_num_to_be_scratched = 0
    p_num_scratched = 0

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
