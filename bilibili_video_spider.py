#!/usr/bin/env python
# -*- coding: utf-8 -*-

import queue
import threading
import json
import argparse
import os
import time
import base64
import subprocess
import math
import re
from threading import Thread

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
import matplotlib.pyplot as plt
import matplotlib.image as mpimg


def log_in():
    login_page_url = "https://passport.bilibili.com/login"  # log in page

    # generates a headless chrome driver
    capability = DesiredCapabilities.CHROME
    capability["pageLoadStrategy"] = "none"

    chrome_options = Options()
    chrome_options.add_argument('--headless')

    global driver
    driver = webdriver.Chrome(options=chrome_options, desired_capabilities=capability)

    # accesses the log in page
    driver.get(login_page_url)

    try:
        wait = WebDriverWait(driver, 20)
        wait.until(ec.presence_of_element_located((By.CLASS_NAME, "qrcode-img")))

        time.sleep(2)

        # gets the html test of the log in page
        login_html_text = driver.page_source

        # gets the qr code
        login_soup = BeautifulSoup(login_html_text, "html.parser")

        div_qrcode_img = login_soup.find("div", "qrcode-img")
        qrcode_img_url = div_qrcode_img.img["src"].split(',')[1:][0]
    except:
        print("{}cannot log in when scratching flv videos. "
              "flv videos can also be scratched, but with lower quality".format(err_msg))
        return

    print("getting qr code for logging in")

    # gets and saves the qr code for logging in
    qrcode_img = base64.urlsafe_b64decode(qrcode_img_url + '=' * (4 - len(qrcode_img_url) % 4))
    with open("qrcode.png", "wb") as f:
        f.write(qrcode_img)

    # displays the qr code
    print("scan the qr code to log in for flv videos of higher qualities")
    print("close the qr code window to retrieve flv videos of lower qualities without logging in")

    qrcode_img = mpimg.imread("qrcode.png")

    # waits for logging in
    start = time.time()

    def close():
        while re.compile(r"注册").search(driver.page_source)\
                and time.time() - start <= 60:
            pass
        plt.close('all')
    Thread(target=close).start()

    plt.imshow(qrcode_img)
    plt.axis(False)
    while plt.get_fignums():
        plt.pause(5)

    # removes the qr code
    os.remove("qrcode.png")

    return driver


def _make_dir(dir_path):
    print("creating dir {} for storing videos".format(dir_path))

    try:
        os.mkdir(dir_path)
    except FileExistsError:
        print(f"{dir_path} already exists")


class BilibiliVideo:
    def __init__(self, bv_num):
        self.bv_num = bv_num if bv_num[:2] != 'BV' else bv_num[2:]

        self.url = f"https://www.bilibili.com/video/BV{self.bv_num}"
        self.av_num, self.video_title, self.ext, self.p_title_list, self.cid_list = BilibiliVideo._get_videos_info(self.url)
        self.total_p_num = len(self.p_title_list)

        self.comment_url = f"https://api.bilibili.com/x/v2/reply?pn=1&type=1&oid={self.av_num}&sort=2"
        self.total_comment_page_num = BilibiliVideo._get_comments_info(self.comment_url)

    @classmethod
    def _get_comments_info(cls, comment_url):
        try:
            r = requests.get(comment_url)
            r.raise_for_status()
        except:
            print(
                "{}cannot get total comment page num".format(err_msg))
        else:
            page = json.loads(r.text)["data"]["page"]
            page_num = math.ceil(page["count"] / page["size"])

            return page_num

    @classmethod
    def _get_window_initial_state_dict(cls, soup):
        # finds the script tag containing all p titles
        script_list = soup.find_all("script")
        window_initial_state = ""
        for script in script_list:
            try:
                if "window.__INITIAL_STATE__={" in script.string:
                    window_initial_state = script.string[25:]
            except:
                pass

        return json.loads(window_initial_state.split(";(function()")[0])

    @classmethod
    def _get_videos_info(cls, root_url):
        try:
            r = requests.get(root_url, headers=headers, timeout=60)
            html_text = r.text
        except:
            print("{}cannot access to {}".format(err_msg, root_url))
            exit(1)
        else:
            soup = BeautifulSoup(html_text, "html.parser")
            # gets window_initial_state dict
            window_initial_state_dict = BilibiliVideo._get_window_initial_state_dict(soup)
            # gets the pages dict
            pages = window_initial_state_dict["videoData"]["pages"]

            # gets the av num
            av_num = window_initial_state_dict["aid"]

            # gets the title of the videos
            video_title = soup.find("h1", "video-title")["title"]

            # gets the page title list of the video
            p_title_list = [page["part"] for page in pages]

            # gets cid list
            cid_list = [page["cid"] for page in pages]

            # gets the ext
            ext = "m4s" if "m4s" in html_text else "flv"

            return av_num, video_title, ext, p_title_list, cid_list


class BilibiliVideoAPage(BilibiliVideo):
    def __init__(self, bilibili_video, p_num):
        super(BilibiliVideoAPage, self).__init__(bilibili_video.bv_num)
        self.url = bilibili_video.url
        self.p_num = p_num

        self.p_url = f"{self.url}?p={self.p_num}"
        # self.p_title = self.p_title_list[self.p_num - 1] if self.total_p_num > 1 else self.video_title
        self.p_title = self.p_title_list[self.p_num - 1]
        self.danmaku_url = f"https://api.bilibili.com/x/v1/dm/list.so?oid={self.cid_list[p_num - 1]}"

        self.audio_url, self.video_url = BilibiliVideoAPage._get_audio_video_url(self.p_url, self.p_num)

    @classmethod
    def _get_html_text(cls, p_url, p_num):
        if not driver:
            # for m4s videos
            try:
                r = requests.get(p_url, headers=headers, timeout=60)
                return r.text
            except:
                print("{}cannot get html text of p{}".format(err_msg, p_num))
        else:
            # for flv videos
            try:
                driver_lock.acquire()
                driver.get(p_url)

                WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.XPATH, "/html/head/script[3]")))
                return driver.page_source
            except:
                print("{}cannot get html text of p{}".format(err_msg, p_num))
            finally:
                driver_lock.release()

    @classmethod
    def _get_script_window_playinfo(cls, soup):
        script_list = soup.find_all("script")
        script_window_playinfo = ""
        for script in script_list:
            try:
                if "window.__playinfo__" in script.string:
                    script_window_playinfo = script.string[20:]
            except:
                pass

        return script_window_playinfo

    @classmethod
    def _get_audio_video_url(cls, p_url, p_num):
        html_text = BilibiliVideoAPage._get_html_text(p_url, p_num)
        if not html_text:
            return

        soup = BeautifulSoup(html_text, "html.parser")
        # retrieves the script tag containing needed download urls
        script_window_playinfo = BilibiliVideoAPage._get_script_window_playinfo(soup)

        audio_url = None
        video_url = None
        try:
            # gets audio url and video url
            playinfo_dict = json.loads(script_window_playinfo)
        except:
            print("{}cannot get <script> with needed urls for p{}".format(err_msg, p_num))
        else:
            try:
                # for m4s videos
                video_url = playinfo_dict["data"]["dash"]["video"][0]["baseUrl"]
                audio_url = playinfo_dict["data"]["dash"]["audio"][0]["baseUrl"]
            except KeyError:
                # for flv videos
                video_url = []
                for durl in playinfo_dict["data"]["durl"]:
                    video_url.append((durl["order"], durl["url"]))
                video_url = sorted(video_url, key=lambda elem: elem[0])
            except:
                print(
                    "{}cannot get download url for p{}".format(err_msg, p_num))

        return audio_url, video_url


class GetUrlThread(threading.Thread):
    def __init__(self, thread_name, bilibili_video, p_num_queue, url_queue):
        super(GetUrlThread, self).__init__()
        self.bilibili_video = bilibili_video
        self.bilibili_video_a_page = None

        self.thread_name = thread_name
        self.p_num_queue = p_num_queue
        self.url_queue = url_queue

    def run(self):
        while not self.p_num_queue.empty():
            # gets a p num
            p_num = self.p_num_queue.get()

            self.bilibili_video_a_page = BilibiliVideoAPage(self.bilibili_video, p_num)

            # puts bilibili_video_a_page into the queue
            self.url_queue.put(self.bilibili_video_a_page)


class DownloadThread(threading.Thread):
    def __init__(self, thread_name, dir_path, url_queue):
        super(DownloadThread, self).__init__()
        self.bilibili_video_a_page = None

        self.dir_path = dir_path
        self.audio_path = ""  # makes sense only for m4s files
        self.video_path = ""
        self.mp4_file_name = ""  # mp4 files generated by combining the audio and video m4s files

        self.thread_name = thread_name
        self.url_queue = url_queue

    def run(self):
        while p_num_scratched < total_p_num_to_be_scratched:
            try:
                # gets a bilibili_video_a_page obj
                self.bilibili_video_a_page = self.url_queue.get(True, timeout=60)

                # saves the audio and video
                self._save_audio_n_video(*self._get_audio_n_video_content())
            except:
                # print("{}{} terminated due to time out "
                #       "when getting download urls from url queue".format(err_msg, self.thread_name))
                break

    def _get_audio_n_video_content(self):
        audio_content = None  # makes sense only for m4s videos
        video_content = None  # originally without sound for m4s videos
        if self.bilibili_video_a_page.audio_url:
            # for m4s videos
            print("downloading audio and video (without sound) \"{}\" in p{}".format(
                self.bilibili_video_a_page.p_title,
                self.bilibili_video_a_page.p_num))

            try:
                audio_content = requests.get(self.bilibili_video_a_page.audio_url,
                                             headers=headers, timeout=60).content
                video_content = requests.get(self.bilibili_video_a_page.video_url,
                                             headers=headers, timeout=60).content
            except:
                print(
                    "{}cannot download data in p{}".format(err_msg, self.bilibili_video_a_page.p_num))
        else:
            # for flv videos
            print("downloading video \"{}\" in p{}".format(self.bilibili_video_a_page.p_title,
                                                           self.bilibili_video_a_page.p_num))

            video_content = []
            flv_lock = threading.Lock()

            def get_flv_content(i, url):
                try:
                    r = requests.get(url, headers=headers, timeout=60)
                    r.raise_for_status()

                    flv_lock.acquire()
                except:
                    print(f"{err_msg}cannot download data of segment {i} in p{self.bilibili_video_a_page.p_num}")
                else:
                    video_content.append((i, r.content))
                finally:
                    flv_lock.release()

            # gets flv video segments
            for (i, url) in self.bilibili_video_a_page.video_url:
                threading.Thread(target=get_flv_content, args=(i, url)).start()

            # waits for all segments to be downloaded
            start = time.time()
            while len(video_content) != len(self.bilibili_video_a_page.video_url)\
                    and time.time() - start <= 10 * 60:
                pass
            if len(video_content) != len(self.bilibili_video_a_page.video_url):
                print(f"{err_msg}cannot retrieve the complete video of p{self.bilibili_video_a_page.p_num}")

            video_content = sorted(video_content, key=lambda elem: elem[0])

        return audio_content, video_content

    def _save_audio_n_video(self, audio_content, video_content):
        # saves the video (and the audio for m4s)
        if self.bilibili_video_a_page.audio_url:
            # for m4s videos
            print("saving audio and video (without sound) \"{}\" in p{}".format(self.bilibili_video_a_page.p_title,
                                                                                self.bilibili_video_a_page.p_num))

            self.audio_path = os.path.join(self.dir_path, "{}_p{}_audio.m4s".format(
                self.bilibili_video_a_page.p_title,
                self.bilibili_video_a_page.p_num))
            self.video_path = os.path.join(self.dir_path, "{}_p{}_video.m4s".format(
                self.bilibili_video_a_page.p_title,
                self.bilibili_video_a_page.p_num))
            self.mp4_file_name = os.path.join(self.dir_path, "p{}_{}.mp4".format(
                self.bilibili_video_a_page.p_num, self.bilibili_video_a_page.p_title))

            with open(self.audio_path, "wb") as f_audio:
                f_audio.write(audio_content)
            with open(self.video_path, "wb") as f_video:
                f_video.write(video_content)

            self._combine()
        else:
            # for flv videos
            print("saving video \"{}\" in p{}".format(self.bilibili_video_a_page.p_title,
                                                      self.bilibili_video_a_page.p_num))

            video_names = [f"p{self.bilibili_video_a_page.p_num}_{i}.flv"
                           for i, _ in self.bilibili_video_a_page.video_url]
            video_paths = [os.path.join(self.dir_path, video_name)
                           for video_name in video_names]
            tmp_txt_path = os.path.join(self.dir_path, f"p{self.bilibili_video_a_page.p_num} files.txt")
            for (i, content) in video_content:
                with open(video_paths[i - 1], "wb") as f:
                    f.write(content)

                with open(tmp_txt_path, 'a') as f:
                    f.write(f"file '{video_names[i - 1]}'\n")

            self.video_path = os.path.join(self.dir_path,
                                           f"{self.bilibili_video_a_page.p_title}_p{self.bilibili_video_a_page.p_num}.flv")
            subprocess.call(
                [f'ffmpeg -f concat -i "{tmp_txt_path}" -c copy "{self.video_path}" &> /dev/null'],
                shell=True
            )

            # removes tmp files and flv segments
            os.remove(tmp_txt_path)
            for video_path in video_paths:
                os.remove(video_path)

        try:
            p_num_scratched_lock.acquire()

            global p_num_scratched
            p_num_scratched += 1
        finally:
            p_num_scratched_lock.release()

    def _combine(self):
        # combines audio and video of the m4s file
        print("combining {} and {} into {}".format(os.path.basename(self.video_path),
                                                   os.path.basename(self.audio_path),
                                                   os.path.basename(self.mp4_file_name)))

        subprocess.call(
            ['ffmpeg -y -i "{}" -i "{}" -codec copy "{}" &> /dev/null'.format(self.video_path, self.audio_path,
                                                                              self.mp4_file_name)],
            shell=True)

        # removes tmp m4s files
        os.remove(self.audio_path)
        os.remove(self.video_path)


def create_queues(from_p_num, to_p_num):
    # creates a queue for storing p numbers
    p_num_queue = queue.Queue()
    # puts p numbers into the queue
    for p_num in range(from_p_num, to_p_num + 1):
        p_num_queue.put(p_num)

    # creates a queue for storing (audio url, video url) of each video
    url_queue = queue.Queue()

    return p_num_queue, url_queue


def create_threads(dir_path, bilibili_video, p_num_queue, url_queue):
    get_url_thread_list = []
    # threads for storing bilibili_video_a_page objs
    for i in range(6):
        get_url_thread = GetUrlThread("get url thread {}".format(i + 1), bilibili_video,
                                      p_num_queue,
                                      url_queue)
        get_url_thread_list.append(get_url_thread)

    download_url_thread_list = []
    # threads for downloading audio (for m4s) and video urls
    for i in range(6):
        download_url_thread = DownloadThread("download url thread {}".format(i + 1), dir_path, url_queue)
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


def validate_p_num(p_num, total_p_num):
    p_nums = p_num.split(',')

    from_p_num = 1
    to_p_num = 1
    if len(p_nums) == 1:
        from_p_num = p_nums[0]
        to_p_num = p_nums[0]
    elif len(p_nums) == 2:
        from_p_num = p_nums[0]
        to_p_num = p_nums[1]
    else:
        print(f"{err_msg}input: 'FROM_P_NUM, TO_P_NUM'")
        exit(5)

    try:
        from_p_num = int(from_p_num)
        to_p_num = int(to_p_num)
    except:
        print(f"{err_msg}p nums should be ints")
        exit(6)

    # checks if from_p_num < to_p_num
    if not from_p_num <= to_p_num:
        print("{}FROM-P-NUM greater than to_p_num".format(err_msg))
        exit(2)
    # checks if from_p_num is greater than 0
    if from_p_num <= 0:
        from_p_num = 1
    # checks if the to p num is out of range
    if to_p_num > total_p_num:
        to_p_num = total_p_num

    return from_p_num, to_p_num


def bilibili_video_spider(bv_num, p_num, root_dir):
    bilibili_video = BilibiliVideo(bv_num=bv_num)

    # generates the headers
    global headers
    headers = {
        'Referer': bilibili_video.url,
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 '
                      'Safari/537.36',
    }

    # simulates logging in if the videos are flv
    global driver
    driver = log_in() if bilibili_video.ext == "flv" else None

    # Validates if the from p num and to p num are valid.
    from_p_num, to_p_num = validate_p_num(p_num, bilibili_video.total_p_num)

    global total_p_num_to_be_scratched
    total_p_num_to_be_scratched = to_p_num - from_p_num + 1

    print("ready to scratch videos from {}: {}".format(bilibili_video.bv_num, bilibili_video.video_title))

    # makes a dir for storing the videos
    dir_path = os.path.join(root_dir, bilibili_video.video_title)
    _make_dir(dir_path)

    # creates a queue for storing p numbers,
    # and a queue for bilibili_video_a_page objs, each of which reprs a p
    p_num_queue, url_queue = create_queues(from_p_num, to_p_num)
    # creates a thread for retrieving bilibili_video_a_page objs,
    # and a thread for downloading and saving videos
    get_url_thread_list, download_thread_list = create_threads(dir_path, bilibili_video, p_num_queue,
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

    headers = None
    driver = None

    total_p_num_to_be_scratched = 0
    p_num_scratched = 0

    err_msg = "bilibili_video_spider.py: error: "

    parser = argparse.ArgumentParser(
        description="bilibili_video_spider.py - a tool for scratching videos from bilibili")

    parser.add_argument("--bv-num", "-b", action="store", required=True,
                        help="bv num of the video to be scratched")
    parser.add_argument("--p-num", "-p", action="store", default="1",
                        help="p number from which videos are to be scratched")
    parser.add_argument("--dir", "-d", action="store", default=os.getcwd(), type=validate_dir,
                        help="directory for storing scratched videos")

    args = parser.parse_args()

    bilibili_video_spider(args.bv_num, args.p_num, args.dir)
