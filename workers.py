#!/usr/bin/python

import beanstalkc
import sqlite3
from gevent import spawn, sleep, monkey; monkey.patch_all()
from bottle import route, error, run, static_file, template, request, abort, redirect, debug, default_app, html_escape
from urllib import quote
from urllib2 import urlopen
from datetime import datetime, timedelta
from time import timezone, strptime, strftime, mktime
from json import loads as json_loads, dumps as json_dumps
from re import compile as re_compile

from queue import *
from data import *

################################################################################
# workers
################################################################################

def check_new_transmissions():
    db_time = data.get_meta('last_transmission_check')
    one_hour_ago = datetime.utcnow() - timedelta(minutes = 60 - (60 + timezone/60))
    try:
        t = strptime(db_time, '%Y-%m-%d %H:%M:%S.%f')
        db_time = datetime(t[0], t[1], t[2], t[3], t[4], t[5])
    except Exception:
        pass

    if db_time == None or db_time < one_hour_ago:
        #print 'checking for new transmissions'
        subscriptions = data.get_userlist('subscriptions')
        for s in subscriptions:
            spawn(get_transmissions, s['ipv6'])

        data.set_meta('last_transmission_check', datetime.utcnow())



def get_transmissions(ipv6):
    queue = Queue()
    since = data.get_latest_telegram(ipv6)
    step = 0
    data.get_profile(ipv6)

    while True:

        try:
            params = '?since=' + since.replace(' ', '%20') + '&step=' + str(step)
            response = urlopen(url='http://[' + ipv6 + ']:3838/api/v1/get_telegrams.json' + params, timeout = 5)
            content = response.read()
            telegrams = json_loads(content)['telegrams']

            if len(telegrams) == 0:
                break

            step = step + 10

        except Exception:
            return False

        for telegram in telegrams:
            text = telegram['text']
            created_at = telegram['created_at']

            try:
                # retransmission
                #print 'importing ' + text.encode('utf-8')

                retransmission_from = telegram['retransmission_from']
                retransmission_original_time = telegram['retransmission_original_time']

                if data.retransmission_exists(retransmission_from, retransmission_original_time):
                    continue

                json = {
                    'job_desc': 'add_telegram',
                    'telegram': {
                        'text': text,
                        'author': ipv6,
                        'created_at': created_at,
                        'retransmission_from': retransmission_from,
                        'retransmission_original_time': retransmission_original_time,
                        'imported': 1,
                    }
                }

                json = json_dumps(json)
                queue.add('write', json)

            except Exception:
                # regular telegram
                #print 'importing ' + text.encode('utf-8')

                # import the telegram
                json = {
                    'job_desc': 'add_telegram',
                    'telegram': {
                        'text': text,
                        'author': ipv6,
                        'created_at': created_at,
                        'imported': 1,
                    }
                }

                json = json_dumps(json)
                queue.add('write', json)

    queue.close()



def write_worker():
    queue = Queue()
    while True:
        job = queue.get_job('write')
        log.debug('got write-job: %s', job.body)

        try:
            job_body = json_loads(job.body)

            if job_body['job_desc'] == 'add_telegram':
                text = job_body['telegram']['text']
                author = job_body['telegram']['author']
                created_at = job_body['telegram']['created_at']
                imported = job_body['telegram']['imported']
                #print job_body

                try:
                    # retransmission
                    retransmission_from = job_body['telegram']['retransmission_from']
                    retransmission_original_time = job_body['telegram']['retransmission_original_time']
                    if not data.telegram_exists(retransmission_from, retransmission_original_time):
                        data.add_telegram(text, author, created_at, imported, retransmission_from, retransmission_original_time)
                except Exception:
                    # regular telegram
                    if not data.telegram_exists(author, created_at):
                        log.debug("dne")
                        data.add_telegram(text, author, created_at, imported)
                        log.debug("after add")

            elif job_body['job_desc'] == 'retransmit_telegram':
                ipv6 = job_body['telegram']['ipv6']
                created_at = job_body['telegram']['created_at']
                data.retransmit_telegram(ipv6, created_at)

            elif job_body['job_desc'] == 'delete_telegram':
                ipv6 = job_body['telegram']['ipv6']
                created_at = job_body['telegram']['created_at']
                data.delete_telegram(ipv6, created_at)

            elif job_body['job_desc'] == 'save_profile':
                profile = job_body['profile']
                user_id = data._get_or_create_userid(profile['ipv6'])
                data.set_user_attr(user_id, 'name', profile['name'])
                data.set_user_attr(user_id, 'bio', profile['bio'])
                data.set_user_attr(user_id, 'transmissions', profile['transmissions'])
                data.set_user_attr(user_id, 'subscribers', profile['subscribers'])
                data.set_user_attr(user_id, 'subscriptions', profile['subscriptions'])

            elif job_body['job_desc'] == 'refresh_counters':
                my_ipv6 = data.get_meta('ipv6')
                user_id = data._get_or_create_userid(my_ipv6)

                # count transmissions
                data.c.execute("""SELECT Count(id)
                FROM telegrams
                WHERE user_id = ?""", (user_id,))
                transmissions_count = data.c.fetchone()[0]

                # count subscribers
                data.c.execute("""SELECT Count(id)
                FROM subscribers""")
                subscribers_count = data.c.fetchone()[0]

                # count subscriptions
                data.c.execute("""SELECT Count(id)
                FROM subscriptions""")
                subscriptions_count = data.c.fetchone()[0]

                data.set_user_attr(user_id, 'transmissions', transmissions_count)
                data.set_user_attr(user_id, 'subscribers', subscribers_count)
                data.set_user_attr(user_id, 'subscriptions', subscriptions_count)

            elif job_body['job_desc'] == 'fetch_remote_profile':
                ipv6 = job_body['ipv6']
                profile = data.get_profile(ipv6)
                db_time = profile['updated_at']
                one_hour_ago = datetime.utcnow() - timedelta(hours = 1 - (1 + timezone/60/60))
                t = strptime(db_time, '%Y-%m-%d %H:%M:%S.%f')
                db_time = datetime(t[0], t[1], t[2], t[3], t[4], t[5])

                if db_time < one_hour_ago:
                    user_id = data._get_or_create_userid(ipv6)
                    data.set_user_attr(user_id, 'name', profile['name'])    # just to refresh updated_at
                    data._fetch_remote_profile(ipv6)

        except Exception as strerr:
            print 'error processing job -', strerr

        job.delete()
        #print 'job finished.'



def notification_worker():
    queue = Queue()
    while True:
        job = queue.get_job('notification')
        log.debug('got notification-job: %s', job.body)

        try:
            job_body = json_loads(job.body)

            if job_body['job_desc'] == 'push_telegram':
                try:
                    # retransmission

                    receiver = job_body['telegram']['receiver']
                    text = job_body['telegram']['text']
                    created_at = job_body['telegram']['created_at']
                    retransmission_from = job_body['telegram']['retransmission_from']
                    retransmission_original_time = job_body['telegram']['retransmission_original_time']

                    json = {
                        'text': text,
                        'created_at': created_at,
                        'retransmission_from': retransmission_from,
                        'retransmission_original_time': retransmission_original_time,
                    }
                    json = json_dumps(json)

                    response = urlopen(url='http://[' + receiver + ']:3838/api/v1/new_telegram',
                        data = 'telegram=' + quote(json),
                        timeout = 60,
                    )
                    content = response.read()
                    result = json_loads(content)['result']

                except Exception:
                    # regular telegram

                    receiver = job_body['telegram']['receiver']
                    text = job_body['telegram']['text']
                    created_at = job_body['telegram']['created_at']

                    json = {
                        'text': text,
                        'created_at': created_at,
                    }
                    json = json_dumps(json)

                    response = urlopen(url='http://[' + receiver + ']:3838/api/v1/new_telegram',
                        data = 'telegram=' + quote(json),
                        timeout = 60,
                    )
                    content = response.read()
                    result = json_loads(content)['result']


                if result == 'unsubscribed':
                    data.remove_subscriber(receiver)

            elif job_body['job_desc'] == 'notify_all_subscribers':
                try:
                    # retransmission

                    text = job_body['telegram']['text']
                    created_at = job_body['telegram']['created_at']
                    retransmission_from = job_body['telegram']['retransmission_from']
                    retransmission_original_time = job_body['telegram']['retransmission_original_time']

                    # push notification
                    subscribers = data.get_all_subscribers()

                    i = -10 #process first 10 without sleep
                    for sub in subscribers:

                        if i % 200 == 0:
                            sleep(1)

                        json = {
                            'job_desc': 'push_telegram',
                            'telegram': {
                                'text': text,
                                'created_at': created_at,
                                'retransmission_from': retransmission_from,
                                'retransmission_original_time': retransmission_original_time,
                                'receiver': sub['ipv6'],
                            }
                        }

                        json = json_dumps(json)
                        queue.add('notification', json)

                        i = i + 1

                except Exception:
                    # regular telegram

                    text = job_body['telegram']['text']
                    created_at = job_body['telegram']['created_at']
                    #print job_body

                    # push notification
                    subscribers = data.get_all_subscribers()

                    i = -10 #process first 10 without sleep
                    for sub in subscribers:

                        if i % 200 == 0:
                            sleep(1)

                        json = {
                            'job_desc': 'push_telegram',
                            'telegram': {
                                'text': text,
                                'created_at': created_at,
                                'receiver': sub['ipv6'],
                            }
                        }

                        json = json_dumps(json)
                        queue.add('notification', json)

                        i = i + 1

        except Exception:
            pass
            #print 'error processing job'

        job.delete()
        #print 'job finished.'
