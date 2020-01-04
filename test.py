#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import queue
import time
import base64
import json

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as ec
# import matplotlib.pyplot as plt
# import matplotlib.image as mpimg

if __name__ == '__main__':
    # # simulates logging in
    # login_page_url = "https://passport.bilibili.com/login"
    #
    # chrome_options = Options()
    # # chrome_options.add_argument('--headless')
    # driver = webdriver.Chrome(options=chrome_options)
    #
    # driver.get(login_page_url)
    # time.sleep(2)
    #
    # login_html_text = driver.page_source
    #
    # # print(login_html_text)
    #
    # # gets qr code
    # login_soup = BeautifulSoup(login_html_text, "html.parser")
    #
    # try:
    #     div_qrcode_img = login_soup.find("div", "qrcode-img")
    #     # qrcode_img_url = div_qrcode_img.img["src"]
    #     # print(qrcode_img_url)
    #     qrcode_img_url = div_qrcode_img.img["src"].split(',')[1:][0]
    #     # print(qrcode_img_url)
    # except:
    #     exit(1)
    # else:
    #     qrcode_img = base64.urlsafe_b64decode(qrcode_img_url + '=' * (4 - len(qrcode_img_url) % 4))
    #     with open("qrcode.png", "wb") as f:
    #         f.write(qrcode_img)
    #
    # # displays the qr code
    # qrcode_img = mpimg.imread("qrcode.png")
    # plt.imshow(qrcode_img)
    # plt.axis(False)
    # plt.show()

    # -----------------
    headers = {
        'Referer': 'https://www.bilibili.com/video/av37947862h',
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.88 Safari/537.36'
    }

    # gets html text
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    driver = webdriver.Chrome(options=chrome_options)

    url = "https://www.bilibili.com/video/av37947862?p=1"

    driver.get(url)

    # html_text = driver.page_source
    # print(html_text)

    html_text = ""
    try:
        element = WebDriverWait(driver, 10).until(ec.presence_of_element_located((By.XPATH, "/html/head/script[3]")))
        html_text = driver.page_source
        # print(html_text)
    except:
        exit(1)

    # gets window.__playinfo__ in a script tag
    soup = BeautifulSoup(html_text, "html.parser")

    script_list = soup.find_all("script")
    script_window_playinfo = ""
    for script in script_list:
        try:
            if "window.__playinfo__" in script.string:
                script_window_playinfo = script.string[20:]
        except:
            pass

    # print(script_window_playinfo)
    playinfo_dict = json.loads(script_window_playinfo)

    video_url = playinfo_dict["data"]["dash"]["video"][0]["baseUrl"]
    audio_url = playinfo_dict["data"]["dash"]["audio"][0]["baseUrl"]

    print(video_url)
    print(audio_url)
