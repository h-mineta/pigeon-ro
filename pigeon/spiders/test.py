# -*- coding: utf-8 -*-

#
# Copyright (c) 2019 h-mineta <h-mineta@0nyx.net>
# This software is released under the MIT License.
#

from pigeon.items import ItemDetail
from scrapy.linkextractors import LinkExtractor
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.spiders import CrawlSpider, Rule
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError
from warnings import filterwarnings
import MySQLdb
import re
import regex
import scrapy

class TestSpider(CrawlSpider):
    name = 'test'

    allowed_domains = [
        'rotool.gungho.jp'
    ]

    def start_requests(self):
        yield scrapy.Request(
            # ギガントブーツ[1]
            # https://rotool.gungho.jp/torihiki/log_detail.php?log=2477791
            'https://rotool.gungho.jp/torihiki/log_detail.php?log={}'.format(2477791),
            meta = {
                'dont_redirect': True
            },
            errback=self.errback_httpbin,
            callback=self.parse_test
        )
        yield scrapy.Request(
            # ライオットチップ[1]
            # https://rotool.gungho.jp/torihiki/log_detail.php?log=2477791
            'https://rotool.gungho.jp/torihiki/log_detail.php?log={}'.format(2532943),
            meta = {
                'dont_redirect': True
            },
            errback=self.errback_httpbin,
            callback=self.parse_test
        )
        yield scrapy.Request(
            # アビスダガー[1]
            # https://rotool.gungho.jp/torihiki/log_detail.php?log=2477791
            'https://rotool.gungho.jp/torihiki/log_detail.php?log={}'.format(2523111),
            meta = {
                'dont_redirect': True
            },
            errback=self.errback_httpbin,
            callback=self.parse_test
        )

    @classmethod
    def from_crawler(cls, crawler):
        return cls(settings = crawler.settings)

    def parse_test(self, response):
        matches = re.search(r"/log_detail.php\?log=([0-9]+)$", response.url)
        if matches is None:
            pass

        # HTMLエスケープされてない箇所を修正
        html_data = response.body.decode('utf-8')
        html_data = regex.sub(r'<([\P{Ascii}]+)>', r'&lt;\1&gt;', html_data)
        #print(html_data)
        html_data = html_data.replace('<Overclock>', '&lt;Overclock&gt;')
        response = response.replace(body=html_data)

        world = response.xpath('//*[@id="tradebox"]/div[1]/div[1]/div[1]/p[1]/text()').get()
        if world is None or world == '':
            self.logger.warning('Got failed response from {} (status:{})'.format(response.url, response.status))
            self.request_loop = False
            pass

        self.logger.info('Got successful response from {}'.format(response.url))

        item = ItemDetail()
        item['id']        = int(matches.group(1))
        item['world']     = response.xpath('//*[@id="tradebox"]/div[1]/div[1]/div[1]/p[1]/text()').get()
        item['datetime']  = response.xpath('//*[@id="tradebox"]/div[1]/div[1]/div[2]/p[1]/text()').get()
        item['item_name'] = response.xpath('//*[@id="tradebox"]/div[1]/div[2]/text()').get()
        item['cost']      = 0
        item['count']     = 0
        item['cards']     = []
        item['enchants']  = []
        item['smelting']  = None

        for list_tr in response.xpath('//*[@id="tradebox"]/div[2]/table[@class="datatable"]/tr'):
            key = list_tr.xpath('th[1]/text()').extract()
            value = list_tr.xpath('td[1]/text()').extract()

            if key[0] == '価格':
                item['cost'] = int(value[0].replace(',',''))
                if item['world'] == 'Noatun':
                    item['cost']*=1000 #1000倍
            elif key[0] == '個数':
                item['count'] = int(value[0].replace(',',''))
            elif key[0] == '精錬値':
                item['smelting'] = int(value[0].replace(',',''))
            elif key[0] == 'カード':
                for val in value:
                    value2 = val.split('・') #・で文字列結合している場合があるため、再度split
                    for val in value2:
                        val = val.strip()
                        if val == 'なし':
                            break
                        elif re.search('カード$', val) \
                            or val == 'アリエス' \
                            or val == 'カプリコーン' \
                            or val == 'キャンサー' \
                            or val == 'サジタリウス' \
                            or val == 'ジェミニ' \
                            or val == 'スコーピオ' \
                            or val == 'タウロス' \
                            or val == 'パイシーズ' \
                            or val == 'リーブラ' \
                            or val == 'レオ' \
                            or val == 'レオの欠片' \
                            or regex.search(r'^魔神の[\P{Ascii}]+\d$', val):
                            item['cards'].append(val)
                        elif val != '':
                            item['enchants'].append(val)

        print(item)
        if item['id'] == 2477791:
            assert item['cards'][0] == '魔神の集中3',"期待する値:魔神の集中3"
            assert item['enchants'][1] == '<超弩級>',"期待する値:<超弩級>"
        if item['id'] == 2532943:
            assert item['enchants'][0] == '<Overclock>',"期待する値:<Overclock>"
        if item['id'] == 2523111:
            assert item['cards'][0] == '魔神の体力3',"期待する値:魔神の体力3"
        pass

    def errback_httpbin(self, failure):
        # log all failures
        self.logger.error(repr(failure))
        self.request_loop = False

        if failure.check(HttpError):
            # you can get the response
            response = failure.value.response
            self.logger.warning('HttpError on {} (status:{})'.format(response.url, response.status))

        #elif isinstance(failure.value, DNSLookupError):
        elif failure.check(DNSLookupError):
            # this is the original request
            request = failure.request
            self.logger.warning('DNSLookupError on {}'.format(request.url))

        #elif isinstance(failure.value, TimeoutError):
        elif failure.check(TimeoutError):
            request = failure.request
            self.logger.warning('TimeoutError on {}'.format(request.url))