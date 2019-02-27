# -*- coding: utf-8 -*-

#
# Copyright (c) 2019 h-mineta <h-mineta@0nyx.net>
# This software is released under the MIT License.
#

from pegion.items import ItemDetail
from scrapy.linkextractors import LinkExtractor
from scrapy.spidermiddlewares.httperror import HttpError
from scrapy.spiders import CrawlSpider, Rule
from twisted.internet.error import DNSLookupError
from twisted.internet.error import TimeoutError
from warnings import filterwarnings
import MySQLdb
import re
import scrapy

class ItemDetailSpider(CrawlSpider):
    name = 'item_detail'

    allowed_domains = [
        'rotool.gungho.jp'
    ]

    request_loop = True

    def __init__(self, settings, *args, **kwargs):
        filterwarnings('ignore', category = MySQLdb.Warning)

        self.mysql_args = {
            'host'       : settings.get('MYSQL_HOST', 'localhost'),
            'port'       : settings.get('MYSQL_PORT', 3306),
            'user'       : settings.get('MYSQL_USER', 'pegion'),
            'passwd'     : settings.get('MYSQL_PASSWORD', 'pegionpw!'),
            'db'         : settings.get('MYSQL_DATABASE', 'pegion'),
            'unix_socket': settings.get('MYSQL_UNIXSOCKET', '/var/lib/mysql/mysql.sock'),
            'charset'    : 'utf8mb4'
        }

    def start_requests(self):
        log_index = 1
        self.connection = MySQLdb.connect(**self.mysql_args)
        self.connection.autocommit(False)

        with self.connection.cursor() as cursor:
            sql_select = '''
                SELECT MAX(id)+1 AS next FROM `item_detail_tbl`;
            '''
            cursor.execute(sql_select)
            for row in cursor:
                log_index = row[0]

        self.connection.close()
        self.connection = None

        while self.request_loop is True:
            yield scrapy.Request(
                'https://rotool.gungho.jp/torihiki/log_detail.php?log={}'.format(log_index),
                meta = {
                    'dont_redirect': True
                },
                errback=self.errback_httpbin,
                callback=self.parse_httpbin
            )
            log_index+=1

    @classmethod
    def from_crawler(cls, crawler):
        return cls(settings = crawler.settings)

    def parse_httpbin(self, response):
        matches = re.search(r"/log_detail.php\?log=([0-9]+)$", response.url)
        if matches is None:
            pass

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
                    val = val.strip().replace('・','')
                    if val == 'なし':
                        break
                    elif re.search('カード$', val):
                        item['cards'].append(val)
                    else:
                        item['enchants'].append(val)

        yield item

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