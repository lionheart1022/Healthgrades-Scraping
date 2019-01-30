# -*- coding: utf-8 -*-#
from __future__ import absolute_import, division, unicode_literals

import scrapy
import re
import urlparse
from scrapy.conf import settings
from scrapy.core.downloader.contextfactory import ScrapyClientContextFactory
from OpenSSL import SSL


class HealthgradesItem(scrapy.Item):
    # define the fields for your item here like:
    url = scrapy.Field()
    # office_information = scrapy.Field()
    # name_of_doctor = scrapy.Field()
    # area_of_specialization = scrapy.Field()
    # phone_number = scrapy.Field()
    # business_name = scrapy.Field()
    # address = scrapy.Field()
    # city = scrapy.Field()
    # state = scrapy.Field()
    # zip = scrapy.Field()
    overview = scrapy.Field()
    experience = scrapy.Field()
    ratings = scrapy.Field()
    insurance = scrapy.Field()
    office_information = scrapy.Field()
    pass


class HealthgradesSpider(scrapy.Spider):
    name = "healthgrades_spider"
    allowed_domains = ['www.healthgrades.com']
    start_url = 'https://www.healthgrades.com/group-directory/fl-florida/ocala/vipcare-oyy217v'

    header = {
        'User-Agent': 'Slackbot-LinkExpanding 1.0 (+https://api.slack.com/robots)'
    }

    def __init__(self, *args, **kwargs):
        super(HealthgradesSpider, self).__init__(
            site_name=self.allowed_domains[0], *args, **kwargs)
        settings.overrides['DOWNLOADER_CLIENTCONTEXTFACTORY'] = 'healthgrades.utils.TLSFlexibleContextFactory'

        # middlewares = settings.get('DOWNLOADER_MIDDLEWARES')
        # settings.overrides['DOWNLOADER_MIDDLEWARES'] = middlewares

    def start_requests(self):
        yield scrapy.Request(self.start_url, callback=self.parse_product, headers=self.header,
                             dont_filter=True)

    def parse_product(self, response):
        item = HealthgradesItem()

        item['url'] = response.url

        office_info_data = response.xpath('//div[@class=""office-info]')

        office_name = office_info_data.xpath('.//*[@class="practiceName"]/text()').extract()
        office_name = office_name[0] if office_name else None

        office_specialty = office_info_data.xpath('.//*[@class="specialty"]/text()').extract()
        office_specialty = office_specialty[0] if office_specialty else None

        office_reviewStar = office_info_data.xpath(
            './/div[@class="reviewStars"]//span[@class="review-count"]/text()').re('\d+')

        office_summaryHours = office_info_data.xpath('.//div[@class="summaryHours"]/strong/text()').extract()
        office_summaryHours = office_summaryHours[0] if office_summaryHours else None

        office_address = office_info_data.xpath(
            './/div[contains(@class, "address")]//*[@itemprop="address"]/*[@itemprop="streetAddress"]/text()').extract()
        office_address = office_address[0] if office_address else None

        office_phone = office_info_data.xpath('.//*[@itemprop="address"]/*[@class="tel"]/text()').extract()
        office_phone = office_phone[0] if office_phone else None

        office_info = {
            'name': office_name,
            'speciality': office_specialty,
            'reviewStar': office_reviewStar,
            'summaryHours': office_summaryHours,
            'address': office_address,
            'phone': office_phone
        }

        item['office_information'] = office_info

        office_providers_data = response.xpath('//div[@class="contentContain"]')

        office_providers = office_providers_data.xpath(
            './/div[@id="component-hgProviders"]//div[@cllass="provider-wrap"]')

        ratings = office_providers_data.xpath('.//div[@itemprop="aggregateRating"]')
        ratingValue = ratings.xpath('.//*[@itemprop="ratingValue"]/@content')[0].extract()
        reviewCount = ratings.xpaths('.//*[@itemprop="reviewCount"]/@content')[0].extract()
        item['ratings'] = {
            'ratingValue': ratingValue,
            'reviewCount': reviewCount
        }

        experience = office_providers_data.xpath('.//div[@class="leanAboutSection"]')
        exp_count = experience.xpath('.//*[contains(@class, "desktop")]/span/text()')[0].extract()
        exp_content = experience.xpath('.//ul[contains(@class, "services-list")]/li/text()').extract()

        item['experience'] = {
            'procedures count': exp_count,
            'content': exp_content
        }

        insurance = office_providers_data.xpath('.//ul[@class="insurance-list"]/li/text()').extract()
        item['insurance'] = insurance

        yield item
