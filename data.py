#!/usr/bin/python

import sqlite3
from gevent import spawn, monkey; monkey.patch_all()
from urllib import quote
from urllib2 import urlopen
from datetime import datetime, timedelta
from time import timezone, strptime
from json import loads as json_loads, dumps as json_dumps

from utils import *
from queue import *

################################################################################
# data class
################################################################################

class Data():
    def __init__(self, db_file):
        self.db = sqlite3.connect(db_file)
        self.c = self.db.cursor()
        try:
            self.c.execute("""SELECT value
            FROM meta
            WHERE key = 'dbversion'""")
            dbversion = self.c.fetchone()[0]
            self.migrate_db(dbversion)
        except Exception:
            log.info('initializing database')
            self.migrate_db(0)

    def migrate_db(self, version):
        version = int(version)
        if version < 1:
            log.info('migrating to version 1')
            self.db.execute("""CREATE TABLE meta (
                id INTEGER PRIMARY KEY,
                key char(50) NOT NULL,
                value char(100) NOT NULL
            )""")
            self.db.execute("""CREATE TABLE telegrams (
                id INTEGER PRIMARY KEY,
                text char(256) NOT NULL,
                user_id INTEGER NULL,
                created_at datetime NOT NULL,
                retransmission_from char(39) NULL,
                retransmission_original_time datetime NULL,
                imported INTEGER DEFAULT 0
            )""")
            self.db.execute("""CREATE TABLE users (
                id INTEGER PRIMARY KEY,
                ipv6 char(39) NOT NULL,
                name char(30) DEFAULT '',
                bio char(256) DEFAULT '',
                transmissions INTEGER DEFAULT 0,
                subscribers INTEGER DEFAULT 0,
                subscriptions INTEGER DEFAULT 0,
                updated_at datetime NULL
            )""")
            self.db.execute("""CREATE TABLE subscribers (
                id INTEGER PRIMARY KEY,
                ipv6 char(39) NOT NULL
            )""")
            self.db.execute("""CREATE TABLE subscriptions (
                id INTEGER PRIMARY KEY,
                ipv6 char(39) NOT NULL
            )""")

            self.db.execute("""INSERT INTO meta (key,value)
            VALUES ('dbversion','1')""")
            self.db.commit()
        if version < 2:
            log.info('migrating to version 2')
            self.db.execute("""CREATE TABLE requests (
                id INTEGER PRIMARY KEY,
                direction char(10) NOT NULL,
                ipv6 char(39) NOT NULL,
                comments char(256) DEFAULT ''
            )""")

            self.db.execute("""UPDATE meta
            SET value = '2'
            WHERE key = 'dbversion'""")
            self.db.commit()
        if version < 3:
            log.info('migrating to version 3')
            self.db.execute("""ALTER TABLE telegrams
            ADD COLUMN mentions TEXT
            """)

            self.db.execute("""UPDATE meta
            SET value = '3'
            WHERE key = 'dbversion'""")
            self.db.commit()
        #if version < 4:
        #    log.info('migrating to version 4')
        #    self.db.execute("""UPDATE meta
        #    SET value = '4'
        #    WHERE key = 'dbversion'""")
        #    self.db.commit()

    def get_meta(self, option_key, default=None):
        try:
            self.c.execute("""SELECT value
            FROM meta
            WHERE key = ?""", (option_key,))

            return self.c.fetchone()[0]

        except Exception:
            return default

    def set_meta(self, option_key, option_value):
        try:
            self.c.execute("""UPDATE meta
            SET value = ?
            WHERE key = ?""", (option_value,option_key))
            if self.c.rowcount <= 0:
                raise
        except Exception:
            self.db.execute("""INSERT INTO meta (key,value)
            VALUES (?,?)""", (option_key,option_value))

        self.db.commit()

    def set_user_attr(self, user_id, key, value):
        now = str(datetime.utcnow())
        self.c.execute("""UPDATE users
        SET """ + key + """ = ?, updated_at = ?
        WHERE id = ?""", (value,now,user_id))

        self.db.commit()

    def _get_or_create_userid(self, ipv6):
        try:
            self.c.execute("""SELECT id
            FROM users
            WHERE ipv6 = ?""", (ipv6,))
            user_id = self.c.fetchone()[0]

            return user_id

        except Exception:
            self.c.execute("""INSERT INTO users (ipv6)
            VALUES (?)""", (ipv6,))
            user_id = self.c.lastrowid
            self.db.commit()

            return user_id

    def ghost_profile(self):
        return {
            'ipv6': '0000:0000:0000:0000:0000:0000:0000:0000',
            'name': 'Nobody',
            'bio': 'Offline. No Teletext.',
            'transmissions': '0',
            'subscribers': '0',
            'subscriptions': '0',
            'updated_at': datetime.utcnow(),
        }

    def get_profile(self, ipv6):
        my_ipv6 = self.get_meta('ipv6')
        user_id = self._get_or_create_userid(ipv6)

        self.c.execute("""SELECT ipv6, name, bio, transmissions, subscribers, subscriptions, updated_at
        FROM users
        WHERE id = ?""", (user_id,))

        result = self.c.fetchone()

        profile = {}
        profile['ipv6'] = result[0]
        profile['name'] = result[1]
        profile['bio'] = format_text(result[2])
        profile['bio_unescaped'] = result[2]
        profile['transmissions'] = result[3]
        profile['subscribers'] = result[4]
        profile['subscriptions'] = result[5]
        profile['updated_at'] = result[6]

        db_time = profile['updated_at']
        try:
            t = strptime(db_time, '%Y-%m-%d %H:%M:%S.%f')
            db_time = datetime(t[0], t[1], t[2], t[3], t[4], t[5])
        except Exception:
            pass

        if db_time == None:
            log.debug('no db time found, new profile, waiting for fetch...')
            profile = self._fetch_remote_profile(ipv6)

        elif db_time < one_hour_ago():
            if my_ipv6 == ipv6:
                self.refresh_counters()
            else:
                log.debug('profile %s is outdated, fetching...', ipv6)
                queue = Queue()

                json = {
                    'job_desc': 'fetch_remote_profile',
                    'ipv6': ipv6
                }

                json = json_dumps(json)
                queue.add('write', json)

                queue.close()

        return profile

    def _fetch_remote_profile(self, ipv6):
        try:
            # bio
            response = urlopen(url='http://[' + ipv6 + ']:3838/api/v1/get_profile.json', timeout = 5)
            content = response.read()
            profile = json_loads(content)['profile']
            profile['ipv6'] = pad_ipv6(ipv6.strip())

            queue = Queue()

            json = {
                'job_desc': 'save_profile',
                'profile': profile
            }

            json = json_dumps(json)
            queue.add('write', json)

            queue.close()

            # avatar
            response = urlopen(url='http://[' + ipv6 + ']:3838/avatar.png', timeout = 5)
            content = response.read()
            f = open('./public/img/profile/' + ipv6 + '.png', 'wb')
            f.write(content)
            f.close()

        except Exception:
            profile = self.ghost_profile()

        return profile

    def refresh_counters(self):
        queue = Queue()

        json = {
            'job_desc': 'refresh_counters',
        }

        json = json_dumps(json)
        queue.add('write', json)

        queue.close()

    def get_telegrams(self, author = False, no_imported = False, step = 0, since = False, fetch_external = False):

        step = str(step)
        my_ipv6 = self.get_meta('ipv6')

        if not author and not no_imported:

            if not since:
                since = '1970-01-01 00:00:00.000000'

            self.c.execute("""SELECT text, mentions, users.name as username, users.ipv6 as ipv6, created_at, retransmission_from, retransmission_original_time
            FROM telegrams
            LEFT JOIN users
            ON telegrams.user_id = users.id
            WHERE created_at > ?
            ORDER BY created_at DESC
            LIMIT 10 OFFSET ? """, (since,step))

        elif author and no_imported:

            if not since:
                since = '1970-01-01 00:00:00.000000'

            self.c.execute("""SELECT text, mentions, users.name as username, users.ipv6 as ipv6, created_at, retransmission_from, retransmission_original_time
            FROM telegrams
            LEFT JOIN users
            ON telegrams.user_id = users.id
            WHERE users.ipv6 = ?
            AND imported = 0
            AND created_at > ?
            ORDER BY created_at DESC
            LIMIT 10 OFFSET ? """, (author,since,step))

        elif not author and no_imported:
            self.c.execute("""SELECT text, mentions, users.name as username, users.ipv6 as ipv6, created_at, retransmission_from, retransmission_original_time
            FROM telegrams
            LEFT JOIN users
            ON telegrams.user_id = users.id
            WHERE imported = 0
            ORDER BY created_at DESC
            LIMIT 10 OFFSET ?""", (step,))

        elif author and not no_imported:
            self.c.execute("""SELECT text, mentions, users.name as username, users.ipv6 as ipv6, created_at, retransmission_from, retransmission_original_time
            FROM telegrams
            LEFT JOIN users
            ON telegrams.user_id = users.id
            WHERE users.ipv6 = ?
            ORDER BY created_at DESC
            LIMIT 10 OFFSET ?""", (author,step))

        result = self.c.fetchall()

        if len(result) == 0 and fetch_external and author != my_ipv6:
            try:
                log.debug('trying to get profile %s...', author)
                profile = self.get_profile(author)
                response = urlopen(url='http://[' + author + ']:3838/api/v1/get_telegrams.json?step=' + str(step), timeout = 5)
                content = response.read()
                telegrams = json_loads(content)['telegrams']

                result = []
                for t in telegrams:
                    try:
                        result.append((t['text'], t['mentions'], profile['name'], author, t['created_at'], t['retransmission_from'], t['retransmission_original_time']))
                    except Exception:
                        result.append((t['text'], t['mentions'], profile['name'], author, t['created_at']))
            except Exception:
                log.debug('%s currently unreachable.', author)
                pass

        telegrams = []

        for res in result:
            text = format_text(res[0])
            text_unescaped = res[0]
            mentions = res[1]
            try:
                mentions = json_loads(mentions)
            except Exception:
                mentions = []
            text = link_mentions(text, mentions)
            author = res[2]
            ipv6 = res[3]
            created_at = res[4]
            created_at_formatted = format_datestring(res[4])
            created_at_pubdate = format_datestring(res[4], True)

            if len(res) > 5 and res[5] != None:
                retransmission_from = res[5]

                try:
                    rt_profile = self.get_profile(retransmission_from)
                    rt_name = rt_profile['name']
                except Exception:
                    rt_name = '[Offline]'

                retransmission_from_author = rt_name
                retransmission_original_time = res[6]
                retransmission_original_time_formatted = format_datestring(res[6])
            else:
                retransmission_from = None
                retransmission_from_author = None
                retransmission_original_time = None
                retransmission_original_time_formatted = None

            telegrams.append({
                'text': text,
                'text_unescaped': text_unescaped,
                'mentions': mentions,
                'author': author,
                'ipv6': ipv6,
                'created_at': created_at,
                'created_at_formatted': created_at_formatted,
                'created_at_pubdate': created_at_pubdate,
                'retransmission_from': retransmission_from,
                'retransmission_from_author': retransmission_from_author,
                'retransmission_original_time': retransmission_original_time,
                'retransmission_original_time_formatted': retransmission_original_time_formatted,
            })

        return telegrams

    def get_single_telegram(self, ipv6, created_at):

        my_ipv6 = self.get_meta('ipv6')

        self.c.execute("""SELECT text, mentions, users.name as username, users.ipv6 as ipv6, created_at, retransmission_from, retransmission_original_time
        FROM telegrams
        LEFT JOIN users
        ON telegrams.user_id = users.id
        WHERE users.ipv6 = ?
        AND created_at = ?
        ORDER BY created_at DESC
        LIMIT 1""", (ipv6,created_at))

        result = self.c.fetchone()

        if (result == None or len(result) == 0) and ipv6 != my_ipv6:
            try:
                response = urlopen(url='http://[' + ipv6 + ']:3838/api/v1/get_single_telegram.json?created_at=' + quote(created_at), timeout = 5)
                content = response.read()
                telegram = json_loads(content)['telegram']

                profile = self.get_profile(ipv6)
                try:
                    result = (telegram['text'], telegram['mentions'], profile['name'], ipv6, telegram['created_at'], telegram['retransmission_from'], telegram['retransmission_original_time'])
                except Exception:
                    result = (telegram['text'], telegram['mentions'], profile['name'], ipv6, telegram['created_at'])
            except Exception:
                pass

        if result != None:
            text = format_text(result[0])
            text_unescaped = result[0]
            mentions = result[1]
            try:
                mentions = json_loads(mentions)
            except Exception:
                mentions = []
            text = link_mentions(text, mentions)
            author = result[2]
            ipv6 = result[3]
            created_at = result[4]
            created_at_formatted = format_datestring(result[4])

            if len(result) > 5 and result[5] != None:
                retransmission_from = result[5]

                try:
                    rt_profile = self.get_profile(retransmission_from)
                    rt_name = rt_profile['name']
                except Exception:
                    rt_name = '[Offline]'

                retransmission_from_author = rt_name
                retransmission_original_time = result[6]
                retransmission_original_time_formatted = format_datestring(result[6])
            else:
                retransmission_from = None
                retransmission_from_author = None
                retransmission_original_time = None
                retransmission_original_time_formatted = None

            telegram = {
                'text': text,
                'text_unescaped': text_unescaped,
                'mentions': mentions,
                'author': author,
                'ipv6': ipv6,
                'created_at': created_at,
                'created_at_formatted': created_at_formatted,
                'retransmission_from': retransmission_from,
                'retransmission_from_author': retransmission_from_author,
                'retransmission_original_time': retransmission_original_time,
                'retransmission_original_time_formatted': retransmission_original_time_formatted,
            }

        else:
            telegram = None

        return telegram

    def get_latest_telegram(self, author):
        self.c.execute("""SELECT created_at
        FROM telegrams
        LEFT JOIN users
        ON telegrams.user_id = users.id
        WHERE users.ipv6 = ?
        ORDER BY created_at DESC
        LIMIT 1""", (author,))

        result = self.c.fetchone()

        try:
            created_at = result[0]
        except Exception:
            created_at = '1970-01-01 00:00:00.000000'

        return created_at

    def telegram_exists(self, author, created_at):
        user_id = self._get_or_create_userid(author)
        self.c.execute("""SELECT id
        FROM telegrams
        WHERE user_id = ?
        AND created_at = ?""", (user_id, created_at))

        return len(self.c.fetchall()) > 0

    def retransmission_exists(self, retransmission_from, retransmission_original_time):
        self.c.execute("""SELECT id
        FROM telegrams
        WHERE retransmission_from = ?
        AND retransmission_original_time = ?""", (retransmission_from, retransmission_original_time))

        return len(self.c.fetchall()) > 0

    def add_telegram(self, text, author, created_at, mentions, imported = '0', retransmission_from = None, retransmission_original_time = None):
        text = text.replace("\r\n", "\n")
        text = text[:256]
        user_id = self._get_or_create_userid(author)
        if len(mentions) > 0:
            mentions = json_dumps(mentions)
        else:
            mentions = None
        self.db.execute("""INSERT INTO telegrams (text,user_id,created_at,mentions,imported,retransmission_from,retransmission_original_time)
        VALUES (?,?,?,?,?,?,?)""", (text,user_id,created_at,mentions,imported,retransmission_from,retransmission_original_time))
        self.db.commit()
        self.refresh_counters()

    def retransmit_telegram(self, author, created_at):
        try:
            queue = Queue()
            telegram = self.get_single_telegram(author, created_at)
            my_ipv6 = self.get_meta('ipv6')
            now = str(datetime.utcnow())
            self.add_telegram(telegram['text_unescaped'], my_ipv6, now, 0, telegram['ipv6'], telegram['created_at'])

            # notify subscribers
            # TODO: mentions
            json = {
                'job_desc': 'notify_all_subscribers',
                'telegram': {
                    'text': telegram['text_unescaped'],
                    'created_at': now,
                    'retransmission_from': telegram['ipv6'],
                    'retransmission_original_time': telegram['created_at'],
                }
            }

            json = json_dumps(json)
            queue.add('notification', json)
            queue.close()

        except Exception as strerr:
            log.warning('retransmission failed: %s', strerr)

    def delete_telegram(self, ipv6, created_at):
        user_id = self._get_or_create_userid(ipv6)
        self.db.execute("""DELETE FROM telegrams
        WHERE user_id = ?
        AND created_at = ?
        LIMIT 1""", (user_id,created_at))
        self.db.commit()

    def get_userlist(self, subscription_type, ipv6 = False, step = 0):
        my_ipv6 = data.get_meta('ipv6')
        step = str(step)
        if subscription_type == 'subscribers':
            subscription_type = 'subscribers'
        elif subscription_type == 'subscriptions':
            subscription_type = 'subscriptions'

        if ipv6 == False or ipv6 == my_ipv6:
            self.c.execute("""SELECT """ + subscription_type + """.ipv6, users.name
            FROM """ + subscription_type + """
            LEFT JOIN users
            ON """ + subscription_type + """.ipv6 = users.ipv6
            ORDER BY """ + subscription_type + """.id DESC
            LIMIT 10 OFFSET ?""", (step,))

            result = self.c.fetchall()
        else:
            try:
                params = '?type=' + subscription_type + '&step=' + step
                response = urlopen(url='http://[' + ipv6 + ']:3838/api/v1/get_subscription.json' + params, timeout = 5)
                content = response.read()
                user_list = json_loads(content)['user_list']
                result = []
                for u in user_list:
                    result.append((u['ipv6'], u['name']))
            except Exception:
                result = []

        user_list = []
        for res in result:
            ipv6 = res[0]
            name = res[1]
            subscribed = self.is_in_subscriptions(ipv6)

            user_list.append({
                'ipv6': ipv6,
                'name': name,
                'subscribed': subscribed,
            })

        return user_list

    def get_all_subscribers(self):
        self.c.execute("""SELECT subscriptions.ipv6, users.name
        FROM subscriptions
        LEFT JOIN users
        ON subscriptions.ipv6 = users.ipv6
        ORDER BY subscriptions.id DESC""")

        result = self.c.fetchall()

        user_list = []
        for res in result:
            ipv6 = res[0]
            name = res[1]

            user_list.append({
                'ipv6': ipv6,
                'name': name,
            })

        return user_list

    def get_all_subscriptions(self):
        self.c.execute("""SELECT subscribers.ipv6
        FROM subscribers
        ORDER BY id ASC""")

        result = self.c.fetchall()

        user_list = []
        for res in result:
            ipv6 = res[0]

            user_list.append({
                'ipv6': ipv6,
            })

        return user_list

    def add_subscriber(self, ipv6):
        if self.is_in_subscribers(ipv6):
            return False

        self.db.execute("""INSERT INTO subscribers (ipv6)
        VALUES (?)""", (ipv6,))
        self.db.commit()
        self.refresh_counters()
        spawn(data.get_profile, ipv6)
        return True

    def remove_subscriber(self, ipv6):
        self.db.execute("""DELETE FROM subscribers
        WHERE ipv6 = ?""", (ipv6,))
        self.db.commit()
        self.refresh_counters()

    def add_subscription(self, ipv6):
        self.db.execute("""INSERT INTO subscriptions (ipv6)
        VALUES (?)""", (ipv6,))
        self.db.commit()
        self.refresh_counters()
        spawn(get_transmissions, ipv6)

    def remove_subscription(self, ipv6):
        self.db.execute("""DELETE FROM subscriptions
        WHERE ipv6 = ?""", (ipv6,))
        self.db.commit()
        self.refresh_counters()

    def is_in_subscriptions(self, ipv6):
        self.c.execute("""SELECT id
        FROM subscriptions
        WHERE ipv6 = ?""", (ipv6,))

        return len(self.c.fetchall()) > 0

    def is_in_subscribers(self, ipv6):
        self.c.execute("""SELECT id
        FROM subscribers
        WHERE ipv6 = ?""", (ipv6,))

        return len(self.c.fetchall()) > 0

    def addr_get_requests(self, direction):
        self.c.execute("""SELECT requests.ipv6, requests.comments, users.name
        FROM requests
        LEFT JOIN users
        ON users.ipv6 = requests.ipv6
        WHERE requests.direction = ?
        ORDER BY requests.id ASC""", (direction,))

        result = self.c.fetchall()

        requests = []
        for res in result:
            ipv6 = res[0]
            comments = res[1]
            name = res[2]

            requests.append({
                'ipv6': ipv6,
                'comments': comments,
                'name': name,
            })

        return requests

    def pending_requests_exist(self):
        self.c.execute("""SELECT id
        FROM requests
        WHERE direction = 'from'""")

        return len(self.c.fetchall()) > 0

    # send or receive
    def addr_add_request(self, direction, ipv6, comments):
        comments = comments.decode('utf-8')
        if self.addr_is_in_requests(direction, ipv6):
            return False

        self.db.execute("""INSERT INTO requests (direction, ipv6, comments)
        VALUES (?,?,?)""", (direction,ipv6,comments))
        self.db.commit()

    # decline or confirm
    def addr_remove_request(self, direction, ipv6):
        self.db.execute("""DELETE FROM requests
        WHERE ipv6 = ?
        AND direction = ?""", (ipv6,direction))
        self.db.commit()

    def addr_is_in_requests(self, direction, ipv6):
        self.c.execute("""SELECT id
        FROM requests
        WHERE ipv6 = ?
        AND direction = ?""", (ipv6,direction))

        return len(self.c.fetchall()) > 0

data = Data('/box/teletext.db')
