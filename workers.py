#!/usr/bin/python

from gevent import spawn, sleep, monkey; monkey.patch_all()
from urllib import quote
from urllib2 import urlopen
from time import strptime
from json import loads as json_loads, dumps as json_dumps
import logging as log
import arrow

from queue import *
from utils import *
import data

################################################################################
# workers
################################################################################

def check_new_transmissions():
    db_time = data.db.get_meta('last_transmission_check')

    if db_time == None or arrow.get(db_time) < one_hour_ago():
        log.info('checking for new transmissions')
        subscriptions = data.db.get_userlist('subscriptions')
        for s in subscriptions:
            spawn(get_transmissions, s['ipv6'])

        data.db.set_meta('last_transmission_check', now_timestamp())



def get_transmissions(ipv6):
    queue = Queue()
    since = data.db.get_latest_telegram(ipv6)
    step = 0
    data.db.get_profile(ipv6)

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
            mentions = telegram['mentions']

            try:
                # retransmission

                retransmission_from = telegram['retransmission_from']
                retransmission_original_time = telegram['retransmission_original_time']

                if data.db.retransmission_exists(retransmission_from, retransmission_original_time):
                    continue

                json = {
                    'job_desc': 'add_telegram',
                    'telegram': {
                        'text': text,
                        'mentions': mentions,
                        'author': ipv6,
                        'created_at': created_at,
                        'retransmission_from': retransmission_from,
                        'retransmission_original_time': retransmission_original_time,
                        'imported': 1,
                    }
                }

                log.debug('importing retransmission: %s', text.encode('utf-8'))
                json = json_dumps(json)
                queue.add('write', json)

            except Exception:
                # regular telegram

                json = {
                    'job_desc': 'add_telegram',
                    'telegram': {
                        'text': text,
                        'author': ipv6,
                        'mentions': mentions,
                        'created_at': created_at,
                        'imported': 1,
                    }
                }

                log.debug('importing regular telegram: %s', text.encode('utf-8'))
                json = json_dumps(json)
                queue.add('write', json)

    queue.close()



def write_worker():
    log.info("spawning write_worker()")
    queue = Queue()
    while True:
        job = queue.get_job('write')
        log.debug('got write-job: %s', job.body)

        try:
            job_body = json_loads(job.body)

            if job_body['job_desc'] == 'add_telegram':
                text = job_body['telegram']['text']
                mentions = job_body['telegram']['mentions']
                author = job_body['telegram']['author']
                created_at = job_body['telegram']['created_at']
                imported = job_body['telegram']['imported']

                try:
                    # retransmission
                    retransmission_from = job_body['telegram']['retransmission_from']
                    retransmission_original_time = job_body['telegram']['retransmission_original_time']
                    if not data.db.telegram_exists(retransmission_from, retransmission_original_time):
                        data.db.add_telegram(text, author, created_at, mentions, imported, retransmission_from, retransmission_original_time, mentions)
                except Exception:
                    # regular telegram
                    if not data.db.telegram_exists(author, created_at):
                        data.db.add_telegram(text, author, created_at, mentions, imported)

            elif job_body['job_desc'] == 'retransmit_telegram':
                ipv6 = job_body['telegram']['ipv6']
                created_at = job_body['telegram']['created_at']
                data.db.retransmit_telegram(ipv6, created_at)

            elif job_body['job_desc'] == 'delete_telegram':
                ipv6 = job_body['telegram']['ipv6']
                created_at = job_body['telegram']['created_at']
                data.db.delete_telegram(ipv6, created_at)

            elif job_body['job_desc'] == 'save_profile':
                profile = job_body['profile']
                user_id = data.db._get_or_create_userid(profile['ipv6'])
                data.db.set_user_attr(user_id, 'name', profile['name'])
                data.db.set_user_attr(user_id, 'bio', profile['bio'])
                data.db.set_user_attr(user_id, 'transmissions', profile['transmissions'])
                data.db.set_user_attr(user_id, 'subscribers', profile['subscribers'])
                data.db.set_user_attr(user_id, 'subscriptions', profile['subscriptions'])

            elif job_body['job_desc'] == 'refresh_counters':
                my_ipv6 = data.db.get_meta('ipv6')
                user_id = data.db._get_or_create_userid(my_ipv6)

                # count transmissions
                data.db.c.execute("""SELECT Count(id)
                FROM telegrams
                WHERE user_id = ?""", (user_id,))
                transmissions_count = data.db.c.fetchone()[0]

                # count subscribers
                data.db.c.execute("""SELECT Count(id)
                FROM subscribers""")
                subscribers_count = data.db.c.fetchone()[0]

                # count subscriptions
                data.db.c.execute("""SELECT Count(id)
                FROM subscriptions""")
                subscriptions_count = data.db.c.fetchone()[0]

                data.db.set_user_attr(user_id, 'transmissions', transmissions_count)
                data.db.set_user_attr(user_id, 'subscribers', subscribers_count)
                data.db.set_user_attr(user_id, 'subscriptions', subscriptions_count)

            elif job_body['job_desc'] == 'fetch_remote_profile':
                ipv6 = job_body['ipv6']
                profile = data.db.get_profile(ipv6)
                db_time = profile['updated_at']

                if arrow.get(db_time) < one_hour_ago():
                    user_id = data.db._get_or_create_userid(ipv6)
                    data.db.set_user_attr(user_id, 'name', profile['name'])    # just to refresh updated_at
                    data.db._fetch_remote_profile(ipv6)

        except Exception as strerr:
            log.error('error processing job: %s', strerr)

        job.delete()
        log.debug('job finished.')



def notification_worker():
    log.info("spawning notification_worker()")
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
                    mentions = job_body['telegram']['mentions']
                    created_at = job_body['telegram']['created_at']
                    retransmission_from = job_body['telegram']['retransmission_from']
                    retransmission_original_time = job_body['telegram']['retransmission_original_time']

                    json = {
                        'text': text,
                        'mentions': mentions,
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
                    mentions = job_body['telegram']['mentions']
                    created_at = job_body['telegram']['created_at']

                    json = {
                        'text': text,
                        'mentions': mentions,
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
                    data.db.remove_subscriber(receiver)

            elif job_body['job_desc'] == 'notify_all_subscribers':
                try:
                    # retransmission

                    text = job_body['telegram']['text']
                    mentions = job_body['telegram']['mentions']
                    created_at = job_body['telegram']['created_at']
                    retransmission_from = job_body['telegram']['retransmission_from']
                    retransmission_original_time = job_body['telegram']['retransmission_original_time']

                    # push notification
                    subscribers = data.db.get_all_subscribers()

                    # add mentions to subscribers
                    try:
                        for m in mentions:
                            for name, ipv6 in m.iteritems():
                                subscribers.append({
                                    'ipv6': ipv6,
                                })

                    except Exception as strerr:
                        log.error("Error adding mentions to subscribers: %s", strerr)

                    i = -10 #process first 10 without sleep
                    for sub in subscribers:

                        if i % 200 == 0:
                            sleep(1)

                        json = {
                            'job_desc': 'push_telegram',
                            'telegram': {
                                'text': text,
                                'mentions': mentions,
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
                    mentions = job_body['telegram']['mentions']
                    created_at = job_body['telegram']['created_at']

                    # push notification
                    subscribers = data.db.get_all_subscribers()

                    # add mentions to subscribers
                    try:
                        for m in mentions:
                            for name, ipv6 in m.iteritems():
                                subscribers.append({
                                    'ipv6': ipv6,
                                })

                    i = -10 #process first 10 without sleep
                    for sub in subscribers:

                        if i % 200 == 0:
                            sleep(1)

                        json = {
                            'job_desc': 'push_telegram',
                            'telegram': {
                                'text': text,
                                'mentions': mentions,
                                'created_at': created_at,
                                'receiver': sub['ipv6'],
                            }
                        }

                        json = json_dumps(json)
                        queue.add('notification', json)

                        i = i + 1

        except Exception as strerr:
            log.error('error processing job: %s', strerr)

        job.delete()
        log.debug('job finished.')
