#!/usr/bin/env python
# -*- coding: utf-8 -*-

# reference; http://d.hatena.ne.jp/miettal/20111229/1325175229

import os
import sys
import ConfigParser
import logging
import logging.config
import re
import datetime
import urllib
import urllib2
import socket
from threading import Timer
from lxml import etree

import tweepy

NICOALERT_CONFIG = os.path.dirname(os.path.abspath(__file__)) + '/nicoalert.config'


class UnexpectedStatusError(Exception):
    def __init__(self, status="n/a"):
        self.status = status

    def __str__(self):
        return 'unexpected status "%s" found.' % self.status


class NicoAlert():
# magic methods
    def __init__(self):
        logging.config.fileConfig(NICOALERT_CONFIG)
        self.logger = logging.getLogger("root")

        self.force_debug_tweet, self.mail, self.password = self.get_basic_config()
        self.logger.info("force_debug_tweet: %s mail: %s password: xxxxx" %
                         (self.force_debug_tweet, self.mail))

        self.target_communities = []
        self.consumer_key = {}
        self.consumer_secret = {}
        self.access_key = {}
        self.access_secret = {}

        for (community, consumer_key, consumer_secret, access_key,
                access_secret) in self.get_community_config():
            self.target_communities.append(community)
            self.consumer_key[self.target_communities[-1]] = consumer_key
            self.consumer_secret[self.target_communities[-1]] = consumer_secret
            self.access_key[self.target_communities[-1]] = access_key
            self.access_secret[self.target_communities[-1]] = access_secret

            self.logger.info("community: %s" % self.target_communities[-1])
            self.logger.info("consumer_key: %s consumer_secret: xxxxx" %
                             self.consumer_key[self.target_communities[-1]])
            self.logger.info("access_key: %s access_secret: xxxxx" %
                             self.access_key[self.target_communities[-1]])

        self.stream_count = 0
        self.previous_stream_count = 0
        self.previous_stream_count_datetime = None

    def __del__(self):
        pass

    # config utility
    def get_basic_config(self):
        config = ConfigParser.ConfigParser()
        config.read(NICOALERT_CONFIG)

        section = "nicoalert"

        try:
            force_debug_tweet = config.get(section, "force_debug_tweet")
            if force_debug_tweet.lower() == "true":
                force_debug_tweet = True
            else:
                force_debug_tweet = False
        except ConfigParser.NoOptionError, unused_e:
            force_debug_tweet = False

        mail = config.get(section, "mail")
        password = config.get(section, "password")

        return force_debug_tweet, mail, password

    def get_community_config(self):
        result = []

        config = ConfigParser.ConfigParser()
        config.read(NICOALERT_CONFIG)

        for section in config.sections():
            matched = re.match(r'community-(.+)', section)
            if matched:
                community = matched.group(1)
                consumer_key = config.get(section, "consumer_key")
                consumer_secret = config.get(section, "consumer_secret")
                access_key = config.get(section, "access_key")
                access_secret = config.get(section, "access_secret")
                result.append(
                    (community, consumer_key, consumer_secret, access_key, access_secret))

        return result

# public methods
    def start_listening_alert(self):
        ticket = self.get_ticket()
        try:
            communities, host, port, thread = self.get_alert_status(ticket)
        except Exception, e:
            self.logger.error("caught exception at get alert status: %s" % e)
            self.logger.error("exit.")
            sys.exit()

        if self.target_communities is None:
            self.logger.warning(
                "target communities is not specified, so use my communities in my account.")
            self.target_communities = communities
        self.logger.info("target communities: %s" % self.target_communities)

        # main loop
        # self.schedule_stream_stat_timer()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.sendall(('<thread thread="%s" version="20061206" res_form="-1"/>' + chr(0)) % thread)

        msg = ""
        while True:
            rcvmsg = sock.recv(1024)
            for ch in rcvmsg:
                if ch == chr(0):
                    # res_data = xml.fromstring(msg)
                    res_data = etree.fromstring(msg)
                    # sample response
                    #{'thread': {'last_res': {'value': '14238750'},
                    #            'resultcode': {'value': '0'},
                    #            'revision': {'value': '1'},
                    #            'server_time': {'value': '1325054571'},
                    #            'thread': {'value': '1000000015'},
                    #            'ticket': {'value': '0x9639240'}}}
                    #{'chat': {'date': {'value': '1325054572'},
                    #          'no': {'value': '14238751'},
                    #          'premium': {'value': '2'},
                    #          'thread': {'value': '1000000015'},
                    #          'user_id': {'value': '394'},
                    #          'value': '75844139,co1140439,13064030'}}

                    try:
                        # 'thread'
                        thread = res_data.xpath("//thread")
                        if thread:
                            self.logger.info("started receiving stream info.")

                        # 'chat'
                        chat = res_data.xpath("//chat")
                        if chat:
                            # self.logger.debug(etree.tostring(chat[0]))
                            value = chat[0].text
                            self.logger.info("received alert: %s" % value)
                            self.handle_chat(value, self.target_communities)
                            self.stream_count += 1
                    except KeyError:
                        self.logger.debug("received unrecognized data.")
                    msg = ""
                else:
                    msg += ch

    # alert handler
    def handle_chat(self, value, communities):
        # value = "102351738,官邸前抗議の首都圏反原発連合と 脱原発を…"
        # value = "102373563,co1299695,7169359"
        values = value.split(',')

        if len(values) == 3:
            # the stream is NOT the official one
            stream_id, community_id, user_id = values
            # self.logger.debug("stream_id: %s community_id: %s user_id: %s" %
            #     (stream_id, community_id, user_id))

            if community_id in communities or self.force_debug_tweet:
                try:
                    community_name, stream_title = self.get_stream_info(stream_id)
                except UnexpectedStatusError, error:
                    self.logger.error(error)
                else:
                    stream_url = "http://live.nicovideo.jp/watch/lv" + stream_id
                    message = "【放送開始】%s（%s）%s" % (
                        stream_title.encode('UTF-8'),
                        community_name.encode('UTF-8'), stream_url)
                    self.logger.info(message)
                    if self.force_debug_tweet:
                        community_id = communities[0]
                    self.update_status(community_id, message)
                if self.force_debug_tweet:
                    os.sys.exit()
            else:
                # self.logger.debug("communityid %s is not target community." % community_id)
                pass

# private methods, niconico
    def get_ticket(self):
        query = {'mail': self.mail, 'password': self.password}
        res = urllib2.urlopen(
            'https://secure.nicovideo.jp/secure/login?site=nicolive_antenna',
            urllib.urlencode(query))

        # res_data = xml.fromstring(res.read())
        res_data = etree.fromstring(res.read())
        # self.logger.debug(etree.tostring(res_data))
        # sample response
        #{'nicovideo_user_response': {'status': {'value': 'ok'},
        #                             'ticket': {'value': 'xxxx'},
        #                             'value': '\n\t'}}

        ticket = res_data.xpath("//ticket")[0].text
        self.logger.debug("ticket: %s" % ticket)

        return ticket

    def get_alert_status(self, ticket):
        query = {'ticket': ticket}
        res = urllib2.urlopen(
            'http://live.nicovideo.jp/api/getalertstatus', urllib.urlencode(query))

        res_data = etree.fromstring(res.read())
        # self.logger.debug(etree.tostring(res_data))
        status = res_data.xpath("//getalertstatus")[0].attrib["status"]
        # sample response
        #{'getalertstatus': {'communities': {'community_id': {'value': 'co9320'}},
        #                    'ms': {'addr': {'value': 'twr02.live.nicovideo.jp'},
        #                           'port': {'value': '2532'},
        #                           'thread': {'value': '1000000015'}},
        #                    'status': {'value': 'ok'},
        #                    'time': {'value': '1324980560'},
        #                    'user_age': {'value': '19'},
        #                    'user_hash': {'value': 'xxxxxxxxxxxxxxxxxxxxxxxxxxx'},
        #                    'user_id': {'value': 'xxxxxxxx'},
        #                    'user_name': {'value': 'miettal'},
        #                    'user_prefecture': {'value': '12'},
        #                    'user_sex': {'value': '1'}}}
        # if res_data.getalertstatus.status != 'ok' :
        if status != 'ok':
            raise UnexpectedStatusError(status)

        # create mycommunities
        communities = []
        for community_id in res_data.xpath("//community_id"):
            communities.append(community_id.text)
        # self.logger.debug(communities)

        host = res_data.xpath("//getalertstatus/ms/addr")[0].text
        port = int(res_data.xpath("//getalertstatus/ms/port")[0].text)
        thread = res_data.xpath("//getalertstatus/ms/thread")[0].text
        self.logger.debug("host: %s port: %s thread: %s" % (host, port, thread))

        return communities, host, port, thread

    def get_stream_info(self, stream_id):
        res = urllib2.urlopen('http://live.nicovideo.jp/api/getstreaminfo/lv' + stream_id)
        xml = res.read()
        # xml = test_stream_info_normal
        # xml = test_stream_info_no_title
        res_data = etree.fromstring(xml)
        self.logger.debug(etree.tostring(res_data))

        # sample response
        #{'getstreaminfo': {'adsense': {'item': {'name': {'value': u'xxxxxxx'},
        #                         'url': {'value': 'http://live.nicovideo.jp/cruise'}}},
        #                   'communityinfo': {'name': {'value': u'xxxxxxx'},
        #                                     'thumbnail': {'value': 'http://xxxxxxx'}},
        #                   'request_id': {'value': 'lv75933298'},
        #                   'status': {'value': 'ok'},
        #                   'streaminfo': {'default_community': {'value': 'co1247778'},
        #                                  'description': {'value': u'xxxxxxx'},
        #                                  'provider_type': {'value': 'community'},
        #                                  'title': {'value': u'xxxxxxx'}}}}

        status = res_data.xpath("//getstreaminfo")[0].attrib["status"]
        # status = "fail"
        if status == "ok":
            community_name = res_data.xpath("//getstreaminfo/communityinfo/name")[0].text
            stream_title = res_data.xpath("//getstreaminfo/streaminfo/title")[0].text
            # set "n/a", when no value provided; like <title/>
            if community_name is None:
                community_name = "n/a"
            if stream_title is None:
                stream_title = "n/a"
        else:
            raise UnexpectedStatusError(status)

        return community_name, stream_title

# private methods, twitter
    def update_status(self, community, status):
        auth = tweepy.OAuthHandler(self.consumer_key[community], self.consumer_secret[community])
        auth.set_access_token(self.access_key[community], self.access_secret[community])
        try:
            tweepy.API(auth).update_status(status)
        except tweepy.error.TweepError, error:
            print u'error in post.'
            print error

    def schedule_stream_stat_timer(self):
        t = Timer(5, self.stream_stat)
        t.start()

    def stream_stat(self):
        current_datetime = datetime.datetime.now()
        if self.previous_stream_count_datetime is not None:
            seconds = (current_datetime-self.previous_stream_count_datetime).seconds
            stream_per_sec = ((float)(self.stream_count - self.previous_stream_count)) / seconds
            self.logger.debug("%.1f streams/sec (interval: %s sec)" % (stream_per_sec, seconds))

        self.previous_stream_count_datetime = current_datetime
        self.previous_stream_count = self.stream_count
        self.schedule_stream_stat_timer()


if __name__ == "__main__":
    nicoalert = NicoAlert()
    nicoalert.start_listening_alert()
