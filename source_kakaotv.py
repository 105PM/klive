# -*- coding: utf-8 -*-
#########################################################
# python
import os
import sys
import logging
import traceback
import json
import re
import urllib
import requests
import threading

# third-party

# sjva 공용

# 패키지
from .plugin import logger, package_name
from .model import ModelSetting, ModelChannel
from source_base import SourceBase

#########################################################

class KakaoItem:
    ch_list = None

    def __init__(self, id, title, url):
        self.id = id.strip()
        self.title = title.strip()
        self.url = url.strip()
        KakaoItem.ch_list[id] = self

class SourceKakaotv(SourceBase):
    @classmethod
    def get_channel_list(cls):
        try:
            tmp = ModelSetting.get('kakaotv_list')
            KakaoItem.ch_list = {}
            ret = []
            for item in tmp.split('\n'):
                if item.strip() == '':
                    continue
                tmp2 = item.split('|')
                if len(tmp2) != 3:
                    continue
                c = ModelChannel(cls.source_name, tmp2[0], tmp2[1], None, True)
                KakaoItem(tmp2[0], tmp2[1], tmp2[2])
                c.current = ''
                ret.append(c)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return ret

    @classmethod
    def get_url(cls, source_id, quality, mode):
        try:
            logger.debug('source_id:%s, quality:%s, mode:%s', source_id, quality, mode)
            tmp = "https://tv.kakao.com/api/v5/ft/livelinks/impress?player=monet_html5&service=kakao_tv&section=kakao_tv&dteType=PC&profile=BASE&liveLinkId={liveid}&withRaw=true&contentType=HLS".format(liveid=KakaoItem.ch_list[source_id].url.split('/')[-1])

            url = requests.get(tmp).json()['raw']['videoLocation']['url']
            if mode == 'web_play':
                return 'return_after_read', url 
            return 'redirect', url
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return

    @classmethod
    def get_return_data(cls, source_id, url, mode):
        try:
            data = requests.get(url).content
            return cls.change_redirect_data(data)
        except Exception as e:
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())
        return data


