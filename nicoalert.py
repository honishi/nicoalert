#!/usr/bin/env python
# -*- coding: utf-8 -*-

# http://d.hatena.ne.jp/miettal/20111229/1325175229

import os
import ConfigParser
import logging
import logging.config 
import datetime
import urllib
import urllib2
import socket
from threading import Timer
from lxml import etree

import tweepy

nicoalert_config = os.path.dirname(os.path.abspath(__file__)) + '/nicoalert.config'

# test data
test_stream_info_normal = '<getstreaminfo status="ok"><request_id>lv102363764</request_id><streaminfo><title>&#12304;&#36196;&#20154;&#12305;&#12496;&#12452;&#12488;&#12414;&#12391;&#12510;&#12452;&#12531;&#12463;&#12521;&#12501;&#12488;&#12304;&#12450;&#12459;&#12488;</title><description>&#21021;&#24515;&#32773;&#12391;&#12377;(&#180;&#12539;&#969;&#12539;`)&#33394;&#12293;&#12431;&#12363;&#12425;&#12394;&#12356;&#12371;&#12392;&#12354;&#12426;&#12377;&#12366;&#12390;&#12290;&#12290;&#12290;&#12522;&#12473;&#12490;&#12540;&#12373;&#12435;&#12395;&#21161;&#12369;&#12425;&#12428;&#12390;&#12414;&#12377;&#65367;&#65367;&#65367;&#12424;&#12363;</description><provider_type>community</provider_type><default_community>co1684688</default_community></streaminfo><communityinfo><name>&#36196;&#20154;&#12398;&#12418;&#12385;&#12419;&#12418;&#12385;&#12419;&#37197;&#20449;&#65288; &#12387; &#180; &#969; &#65344; &#65347; &#65289;</name><thumbnail>http://icon.nimg.jp/community/s/168/co1684688.jpg?1341243427</thumbnail></communityinfo><adsense><item><name>&gt;&gt;&#12491;&#12467;&#29983;&#12463;&#12523;&#12540;&#12474;&#12391;&#20182;&#12398;&#30058;&#32068;&#12434;&#25506;&#12377;</name><url>http://live.nicovideo.jp/cruise</url></item></adsense></getstreaminfo>'
test_stream_info_no_title = '<getstreaminfo status="ok"><request_id>lv102363769</request_id><streaminfo><title/><description>&#12424;&#12369;&#12428;&#12400;&#12289;&#12467;&#12513;&#12531;&#12488;&#12394;&#12393;&#12394;&#12393;&#12375;&#12390;&#12356;&#12387;&#12390;&#12367;&#12384;&#12373;&#12356;&#12394;&#65367;&#65367;&#65367;&#65367;&#25237;&#31295;&#21205;&#30011;&#12539;http://www.nicovideo.jp/watch/13</description><provider_type>community</provider_type><default_community>co1645552</default_community></streaminfo><communityinfo><name>&#9734;&#65302;&#21495;&#12392;&#24841;&#24555;&#12394;&#12522;&#12473;&#12490;&#12540;&#36948;&#12392;&#12381;&#12398;&#20182;&#12418;&#12429;&#12418;&#12429;&#12398;&#38598;&#12356;&#12398;&#22580;&#9734;</name><thumbnail>http://icon.nimg.jp/community/s/164/co1645552.jpg?1337421832</thumbnail></communityinfo><adsense><item><name>&gt;&gt;&#12491;&#12467;&#29983;&#12463;&#12523;&#12540;&#12474;&#12391;&#20182;&#12398;&#30058;&#32068;&#12434;&#25506;&#12377;</name><url>http://live.nicovideo.jp/cruise</url></item></adsense></getstreaminfo>'

# 
class UnexpectedStatusError(Exception):
    def __init__(self, status):
        self.status = status

    def __str__(self):
        return 'unexpected status "%s" found.' % self.status

#
class NicoAlert():
# class lifecycle
    def __init__(self):
        logging.config.fileConfig(nicoalert_config)
        self.logger = logging.getLogger("root")
        (self.force_debug_tweet, self.mail, self.password,
            self.target_communities) = self.get_config()
        if self.force_debug_tweet:
            print "debug"
        else:
            print "not debug"

        self.twitter = self.get_twitter()

        self.stream_count = 0
        self.previous_stream_count = 0
        self.previous_stream_count_datetime = None

    def __del__(self):
        pass

# utility
    def get_config(self):
        config = ConfigParser.ConfigParser()
        config.read(nicoalert_config)
        if config.get("nicoalert", "force_debug_tweet").lower() == "true":
            force_debug_tweet = True
        else:
            force_debug_tweet = False
        mail = config.get("nicoalert", "mail")
        password = config.get("nicoalert", "password")
        try:
            target_communities = config.get("nicoalert", "target_communities").split(',')
        except ConfigParser.NoOptionError, unused_error:
            target_communities = None

        # self.logger.debug("mail: %s password: *** target_communities: %s" % (mail, target_communities))

        return force_debug_tweet, mail, password, target_communities

# twitter

# twitter
    def get_twitter(self):
        config = ConfigParser.ConfigParser()
        config.read(nicoalert_config)

        consumer_key = config.get("twitter", "consumer_key")
        consumer_secret = config.get("twitter", "consumer_secret")
        access_key = config.get("twitter", "access_key")
        access_secret = config.get("twitter", "access_secret")

        self.logger.debug("consumer_key: %s consumer_secret: ***"
            "access_key: %s access_secret: ***" %
            (consumer_key, access_key))

        auth = tweepy.OAuthHandler(consumer_key, consumer_secret)
        auth.set_access_token(access_key, access_secret)

        return tweepy.API(auth)

    def update_status(self, status):
        try:
            self.twitter.update_status(status)
        except tweepy.error.TweepError, error:
            print u'error in post.'
            print error

    def remove_all(self):
        for status in tweepy.Cursor(self.twitter.user_timeline).items(1000):
            try:
                self.twitter.destroy_status(status.id)
            except tweepy.error.TweepError, error:
                print u'error in post destroy'
                print error
            # sys.stdout.flush()

    def schedule_stream_stat_timer(self):
        t = Timer(5, self.stream_stat)
        t.start()

        return

    def stream_stat(self):
        current_datetime = datetime.datetime.now()
        if self.previous_stream_count_datetime is not None:
            seconds = (current_datetime-self.previous_stream_count_datetime).seconds
            stream_per_sec = ((float)(self.stream_count - self.previous_stream_count)) / seconds
            self.logger.debug("%.1f streams/sec (interval: %s sec)" % (stream_per_sec, seconds))

        self.previous_stream_count_datetime = current_datetime
        self.previous_stream_count = self.stream_count
        self.schedule_stream_stat_timer()

        return
# nico
    def get_ticket(self):
        query = {'mail':self.mail, 'password':self.password}
        res = urllib2.urlopen('https://secure.nicovideo.jp/secure/login?site=nicolive_antenna',
        urllib.urlencode(query))

        # res_data = xml.fromstring(res.read())
        res_data = etree.fromstring(res.read())
        # self.logger.debug(etree.tostring(res_data))
        # sample response
        #{'nicovideo_user_response': {'status': {'value': 'ok'},
        #                             'ticket': {'value': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'},
        #                             'value': '\n\t'}}

        ticket = res_data.xpath("//ticket")[0].text
        self.logger.debug("ticket: %s" % ticket)

        return ticket

    def get_alert_status(self, ticket):
        query = {'ticket':ticket}
        res = urllib2.urlopen('http://live.nicovideo.jp/api/getalertstatus', urllib.urlencode(query))

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
        if status != 'ok' :
            raise NICOAlertAuthorizeError

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
        res = urllib2.urlopen('http://live.nicovideo.jp/api/getstreaminfo/lv'+stream_id)
        xml = res.read()
        # xml = test_stream_info_normal
        # xml = test_stream_info_no_title
        res_data = etree.fromstring(xml)
        self.logger.debug(etree.tostring(res_data))

        # sample response
        #{'getstreaminfo': {'adsense': {'item': {'name': {'value': u'xxxxxxx'},
        #                                        'url': {'value': 'http://live.nicovideo.jp/cruise'}}},
        #                   'communityinfo': {'name': {'value': u'xxxxxxx'},
        #                                     'thumbnail': {'value': 'http://xxxxxxx'}},
        #                   'request_id': {'value': 'lv75933298'},
        #                   'status': {'value': 'ok'},
        #                   'streaminfo': {'default_community': {'value': 'co1247778'},
        #                                  'description': {'value': u'xxxxxxx'},
        #                                  'provider_type': {'value': 'community'},
        #                                  'title': {'value': u'xxxxxxx'}}}}

        status = res_data.xpath("//getstreaminfo")[0].attrib["status"]
        # test
        # status = "fail"
        if status == "ok":
            community_name = res_data.xpath("//getstreaminfo/communityinfo/name")[0].text
            stream_title = res_data.xpath("//getstreaminfo/streaminfo/title")[0].text
            # set "n/a", when no value provided; like <title/>
            if community_name is None: community_name = "n/a"
            if stream_title is None: stream_title = "n/a"
        else:
            raise UnexpectedStatusError(status)

        return community_name, stream_title

# main
    def tweet_message(self, message):
        try:
            self.update_status(message)
        except Exception, error:
            self.logger.debug("error in tweet: %s" % error)

    def handle_chat(self, value, communities):
        # value = "102351738,官邸前抗議の首都圏反原発連合と 脱原発を…"
        # value = "102373563,co1299695,7169359"
        # stream_id, community_id, user_id = value.split(',')
        values = value.split(',')

        if len(values) == 3:
            # the stream is NOT the official one
            stream_id, community_id, user_id = values
            # self.logger.debug("stream_id: %s community_id: %s user_id: %s" % (stream_id, community_id, user_id))

            if community_id in communities or self.force_debug_tweet:
                try:
                    community_name, stream_title = self.get_stream_info(stream_id)
                except UnexpectedStatusError, error:
                    self.logger.debug(error)
                # except:
                #     self.logger.debug("?")
                else:
                    stream_url = "http://live.nicovideo.jp/watch/lv" + stream_id
                    message = "「%s」で「%s」が放送開始しました。" % (community_name.encode('UTF-8'), stream_title.encode('UTF-8'))
                    self.logger.debug(message + stream_url)
                    self.tweet_message(message + stream_url)
                if self.force_debug_tweet:
                    os.sys.exit()

            else:
                # self.logger.debug("communityid %s is not target community." % community_id)
                pass

        return

    def go(self):
        ticket = self.get_ticket()
        communities, host, port, thread = self.get_alert_status(ticket)

        if self.target_communities is None:
            self.logger.debug("target communities is not specified, so use my communities in my account.")
            self.target_communities = communities
        self.logger.debug("target communities: %s" % self.target_communities)

        # main loop
        # self.schedule_stream_stat_timer()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))
        sock.sendall(('<thread thread="%s" version="20061206" res_form="-1"/>'+chr(0)) % thread)

        msg = ""
        while True :
            rcvmsg = sock.recv(1024)
            for ch in rcvmsg:
                if ch == chr(0) :
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
                        thread = res_data.xpath("//tread")
                        if thread:
                            self.logger.debug("番組通知の受信を開始しました．")
        
                        # 'chat'
                        chat = res_data.xpath("//chat")
                        if chat:
                            # self.logger.debug(etree.tostring(chat[0]))
                            value = chat[0].text
                            # self.logger.debug("---------- ---------- ---------")
                            self.logger.debug(value)
                            self.handle_chat(value, self.target_communities)
                            self.stream_count += 1
                    except KeyError:
                        self.logger.debug("その他のデータを受信しました．")
                    msg = ""
                else :
                    msg += ch

if __name__ == "__main__":
    nicoalert = NicoAlert()
    nicoalert.go()
