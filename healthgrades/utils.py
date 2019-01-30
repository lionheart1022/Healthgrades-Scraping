import os
import pickle
import re
import time
import traceback
import random
import urlparse
import json

import boto
from boto.s3.key import Key
from OpenSSL import SSL

from scrapy.conf import settings
from scrapy.contrib.downloadermiddleware.cookies import CookiesMiddleware
from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory
from twisted.internet._sslverify import ClientTLSOptions


from twisted.internet.ssl import ClientContextFactory

true_args_values = (1, '1', 'true', 'True', True)
false_args_values = (0, '0', 'false', 'False', False, None)


class ProxyConfig():
    def __init__(self, spider_name):
        self.amazon_bucket_name = "sc-settings"
        self.production_bucket_config_filename = "global_proxy_config.cfg"
        self.master_bucket_config_filename = "master_proxy_config.cfg"
        self.branch_path = '/tmp/branch_info.txt'
        self.current_branch = self.get_current_branch()
        self.spider_name = spider_name

    def get_current_branch(self):
        if os.path.isfile(self.branch_path):
            with open(self.branch_path) as gittempfile:
                branch_name = gittempfile.readline().strip()
        else:
            branch_name = "sc_production"
        return branch_name

    def get_config_filename(self, branch_name):
        if branch_name == "sc_production":
            config_filename = self.production_bucket_config_filename
        else:
            config_filename = self.master_bucket_config_filename
        return config_filename

    def get_spider_short_name(self, spider_name):
        return spider_name.replace("_shelf_urls_products", "").replace("_products", "")

    def get_config(self):
        spider_short_name = self.get_spider_short_name(self.spider_name)
        config_filename = self.get_config_filename(self.current_branch)
        config = self.get_proxy_config_file(config_filename)

        if config and spider_short_name:
            if spider_short_name in config:
                spider_config = config.get(spider_short_name, {})
            else:
                spider_config = config.get("default", {})
            return spider_config

    def get_proxy(self):
        chosen_proxy = self._weighted_choice(self.get_config())
        return "http://" + chosen_proxy

    def get_proxy_config_file(self, bucket_config_filename):
        proxy_config = None
        try:
            S3_CONN = boto.connect_s3(is_secure=False)
            S3_BUCKET = S3_CONN.get_bucket(self.amazon_bucket_name, validate=False)
            k = Key(S3_BUCKET)
            k.key = bucket_config_filename
            value = k.get_contents_as_string()
            proxy_config = json.loads(value)
        except:
            print(traceback.format_exc())
        return proxy_config

    def _weighted_choice(self, choices_dict):
        choices = [(key, value) for (key, value) in choices_dict.items()]
        total = sum(w for c, w in choices)
        r = random.uniform(0, total)
        upto = 0
        for c, w in choices:
            if upto + w >= r:
                return c
            upto += w

def get_canonical_url(response):
    canonical_url = response.xpath('//link[@rel="canonical"]/@href').extract()
    if canonical_url:
        return urlparse.urljoin(response.url, canonical_url[0])

def get_random_positive_float_number():
    return round(random.uniform(0.01, 100.00), 2)

def is_empty(x, y=None):
    if x:
        return x[0]
    else:
        return y

def valid_url(url):
    if not re.findall(r"^http(s)?://", url):
        url = "http://" + url
    return url

def is_valid_url(url):
    return bool(re.findall(r"^http(s)?://", url))

def replace_http_with_https(url):
    return re.sub('^http://', 'https://', url)

def extract_first(selector_list, default=None):
    for x in selector_list:
        return x.extract()
    else:
        return default

def _find_between(s, first, last, offset=0):
    try:
        s = s.decode("utf-8")
        start = s.index(first, offset) + len(first)
        end = s.index(last, start)
        return s[start:end]
    except ValueError:
        return ""

def _init_chromium():
    from selenium import webdriver
    import socket

    socket.setdefaulttimeout(60)
    executable_path = '/usr/sbin/chromedriver'
    if not os.path.exists(executable_path):
        executable_path = '/usr/local/bin/chromedriver'
    options = webdriver.ChromeOptions()
    options.add_argument('--headless')
    options.add_argument('--disable-gpu')
    driver = webdriver.Chrome(executable_path=executable_path,
                              chrome_options=options)
    return driver

def urlEncodeNonAscii(b):
    return re.sub('[\x80-\xFF]', lambda c: '%%%02x' % ord(c.group(0)), b)

def upc_check_digit(upc):
    upc_str = str(upc)
    if len(upc_str) < 10 and len(upc_str) > 12:
        return upc_str.zfill(12)[:12]
    elif len(upc_str) == 12:
        return upc_str
    elif len(upc_str) == 10:
        upc_str = '0' + upc_str
    s = 0
    for i in upc[::2]:
        s += 3 * int(i)
    for i in upc[1::2]:
        s += int(i)
    upc_str += str(-s % 10)
    return upc_str

class SharedCookies(object):

    TIMEOUT = 60

    cookies = None
    shared_cookies = None
    shared_cookies_lock = None

    def __init__(self, key, bucket='sc-settings'):
        # hook shared cookies
        middlewares = settings['DOWNLOADER_MIDDLEWARES']
        middlewares['scrapy.contrib.downloadermiddleware.cookies.CookiesMiddleware'] = None
        middlewares['product_ranking.utils.SharedCookiesMiddleware'] = 700
        settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

        self.bucket = bucket
        self.key = key

        try:
            s3_conn = boto.connect_s3(is_secure=False)
            s3_bucket = s3_conn.get_bucket(self.bucket, validate=False)
            self.shared_cookies = Key(s3_bucket)
            self.shared_cookies.key = '{}.cookies'.format(self.key)
            if not self.shared_cookies.exists():
                self.shared_cookies.set_contents_from_string('')

            self.shared_cookies_lock = Key(s3_bucket)
            self.shared_cookies_lock.key = '{}.lock'.format(self.key)
            if not self.shared_cookies_lock.exists():
                self.shared_cookies_lock.set_contents_from_string('')
        except:
            print(traceback.format_exc())

    def set(self, cookies):
        try:
            self.shared_cookies.set_contents_from_string(pickle.dumps(cookies))
            self.cookies = cookies

            return True
        except:
            print(traceback.format_exc())

        return False

    def get(self):
        if self.cookies:
            return self.cookies

        try:
            start_time = time.time()

            while time.time() - start_time < self.TIMEOUT:
                if not self.is_locked():
                    break

                time.sleep(1)

            content = self.shared_cookies.get_contents_as_string()
            if content:
                self.cookies = pickle.loads(self.shared_cookies.get_contents_as_string())

                return self.cookies
        except:
            print(traceback.format_exc())

        return False

    def delete(self):
        try:
            self.shared_cookies.set_contents_from_string('')
            self.cookies = None

            return True
        except:
            print(traceback.format_exc())

        return False

    def lock(self):
        try:
            self.shared_cookies_lock.set_contents_from_string('1')

            return True
        except:
            print(traceback.format_exc())

        return False

    def is_locked(self):
        try:
            if self.shared_cookies_lock.get_contents_as_string():
                return True
        except:
            print(traceback.format_exc())

        return False

    def unlock(self):
        try:
            self.shared_cookies_lock.set_contents_from_string('')

            return True
        except:
            print(traceback.format_exc())

        return False


class SharedCookiesMiddleware(CookiesMiddleware):

    def process_request(self, request, spider):
        if not spider.shared_cookies.is_locked():
            shared_cookies = spider.shared_cookies.get()

            if shared_cookies:
                self.jars = shared_cookies

        return super(SharedCookiesMiddleware, self).process_request(request, spider)

    def process_response(self, request, response, spider):
        if spider.shared_cookies.is_locked():
            spider.shared_cookies.set(self.jars)

        return super(SharedCookiesMiddleware, self).process_response(request, response, spider)


class TLSFlexibleContextFactory(ScrapyClientContextFactory):
    """A more protocol-flexible TLS/SSL context factory.

    A TLS/SSL connection established with [SSLv23_METHOD] may understand
    the SSLv3, TLSv1, TLSv1.1 and TLSv1.2 protocols.
    See https://www.openssl.org/docs/manmaster/ssl/SSL_CTX_new.html
    """

    def __init__(self):
        self.method = SSL.SSLv23_METHOD


class CustomClientContextFactory(ScrapyClientContextFactory):
    def getContext(self, hostname=None, port=None):
        ctx = ClientContextFactory.getContext(self)
        ctx.set_options(SSL.OP_ALL)
        if hostname:
            ClientTLSOptions(hostname, ctx)
        return ctx
