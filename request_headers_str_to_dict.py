example = """Accept: */*
Accept-Encoding: gzip, deflate, br
Accept-Language: en-US,en;q=0.9,zh-CN;q=0.8,zh-TW;q=0.7,zh;q=0.6,ja;q=0.5
Connection: keep-alive
Host: cn-gdzj-bn-bcache-01.bilivideo.com
Origin: https://www.bilibili.com
Referer: https://www.bilibili.com/video/BV1MW411w79n?p=1
Sec-Fetch-Dest: empty
Sec-Fetch-Mode: cors
Sec-Fetch-Site: cross-site
User-Agent: Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/81.0.4044.138 Safari/537.36"""

request_header_str = input("request header:")

header_list = request_header_str.split('\n')
headers = {header.split(": ")[0]: header.split(": ")[1]
           for header in header_list}

print(headers)
