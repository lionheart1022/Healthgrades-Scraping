# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class HealthgradesItem(scrapy.Item):
    # define the fields for your item here like:
    url = scrapy.Field()
    office_information = scrapy.Field()
    name_of_doctor = scrapy.Field()
    area_of_specialization = scrapy.Field()
    phone_number = scrapy.Field()
    business_name = scrapy.Field()
    address = scrapy.Field()
    city = scrapy.Field()
    state = scrapy.Field()
    zip = scrapy.Field()
    experience = scrapy.Field()
    ratings = scrapy.Field()
    insurance = scrapy.Field()
    pass
