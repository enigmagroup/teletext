#!/usr/bin/python

from bottle import route, error, run, static_file, template, request, abort, redirect, debug, default_app, html_escape
from json import loads as json_loads, dumps as json_dumps

from utils import *
import data
import logging as log

################################################################################
# API
################################################################################

@route('/api/v1/ping')
def api_ping():
    return {"result": "pong"}



@route('/api/v1/get_telegrams.json')
def telegrams_json():
    step = request.GET.get('step', 0)
    since = request.GET.get('since', False)
    ipv6 = data.db.get_meta('ipv6')
    telegrams = data.db.get_telegrams(author = ipv6, no_imported = True, step = step, since = since)

    for key, val in enumerate(telegrams):
        # only keep text, created_at, mentions, and retransmission_from+orgtime if set
        telegrams[key]['text'] = telegrams[key]['text_unescaped']
        del(telegrams[key]['text_unescaped'])
        del(telegrams[key]['author'])
        del(telegrams[key]['ipv6'])
        del(telegrams[key]['created_at_formatted'])
        del(telegrams[key]['created_at_pubdate'])
        del(telegrams[key]['retransmission_from_author'])
        del(telegrams[key]['retransmission_original_time_formatted'])

        if telegrams[key]['retransmission_from'] == None:
            del(telegrams[key]['retransmission_from'])
            del(telegrams[key]['retransmission_original_time'])

    return {"telegrams": telegrams}



@route('/api/v1/get_single_telegram.json')
def single_telegram_json():
    my_ipv6 = data.db.get_meta('ipv6')
    created_at = request.GET.get('created_at')
    telegram = data.db.get_single_telegram(my_ipv6, created_at)

    if telegram:
        # only keep text, created_at, mentions, and retransmission_from+orgtime if set
        telegram['text'] = telegram['text_unescaped']
        del(telegram['text_unescaped'])
        del(telegram['author'])
        del(telegram['ipv6'])
        del(telegram['created_at_formatted'])

        if telegram['retransmission_from'] == None:
            del(telegram['retransmission_from'])
            del(telegram['retransmission_from_author'])
            del(telegram['retransmission_original_time'])
            del(telegram['retransmission_original_time_formatted'])

    return {"telegram": telegram}



@route('/api/v1/new_telegram', method = 'POST')
def api_new_telegram():
    result = 'failed'

    telegram = request.POST.get('telegram', '').strip()

    if telegram != '':
        try:
            telegram = json_loads(telegram)
            text = telegram['text']
            mentions = telegram['mentions']
            try:
                mentions = json_loads(mentions)
            except Exception:
                mentions = []
            ipv6 = pad_ipv6(get_real_ip())
            created_at = telegram['created_at']

            if not data.db.is_in_subscriptions(ipv6):
                return {"result": "unsubscribed"}

            try:
                # retransmission

                retransmission_from = telegram['retransmission_from']
                retransmission_original_time = telegram['retransmission_original_time']

                if data.db.retransmission_exists(retransmission_from, retransmission_original_time):
                    return {"result": "failed"}

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

                json = json_dumps(json)

                queue = Queue()
                queue.add('write', json)
                log.debug('write-job added via API to queue: %s', json)
                queue.close()

                result = 'success'

            except Exception:
                # regular telegram

                json = {
                    'job_desc': 'add_telegram',
                    'telegram': {
                        'text': text,
                        'mentions': mentions,
                        'author': ipv6,
                        'created_at': created_at,
                        'imported': 1,
                    }
                }

                json = json_dumps(json)

                queue = Queue()
                queue.add('write', json)
                log.debug('write-job added via API to queue: %s', json)
                queue.close()

                result = 'success'

        except Exception as strerr:
            log.error('Error adding telegram: %s', strerr)
            result = 'error'

    return {"result": result}



@route('/api/v1/get_profile.json')
def profile_json():
    my_ipv6 = data.db.get_meta('ipv6')
    profile = data.db.get_profile(my_ipv6)

    del(profile['ipv6'])
    del(profile['updated_at'])
    profile['bio'] = profile['bio_unescaped']
    del(profile['bio_unescaped'])

    return {"profile": profile}



@route('/avatar.png')
def external_profile_image():
    ipv6 = data.db.get_meta('ipv6')
    return static_file('/img/profile/' + ipv6 + '.png', root = './public')



@route('/api/v1/get_subscription.json')
def get_subscription():

    subscription_type = request.GET.get('type')
    step = request.GET.get('step', 0)

    if subscription_type == 'subscribers':
        show_subscribers = data.db.get_meta('show_subscribers', '0')
        if show_subscribers == '1':
            user_list = data.db.get_userlist(subscription_type = 'subscribers', step = step),

    elif subscription_type == 'subscriptions':
        show_subscriptions = data.db.get_meta('show_subscriptions', '0')
        if show_subscriptions == '1':
            user_list = data.db.get_userlist(subscription_type = 'subscriptions', step = step),

    try:
        user_list = user_list[0]
    except Exception:
        user_list = {}

    # kick unnecessary fields
    for key, val in enumerate(user_list):
        del(user_list[key]['subscribed'])

    return {"user_list": user_list}



@route('/api/v1/subscribe', method = 'POST')
def external_subscribe():
    try:
        ipv6 = pad_ipv6(get_real_ip())
        data.db.add_subscriber(ipv6)
        result = 'success'
    except Exception as strerr:
        log.error(strerr)
        result = 'failed'

    return {"result": result}



@route('/api/v1/unsubscribe', method = 'POST')
def external_unsubscribe():
    try:
        ipv6 = pad_ipv6(get_real_ip())
        data.db.remove_subscriber(ipv6)
        result = 'success'
    except Exception as strerr:
        log.error(strerr)
        result = 'failed'

    return {"result": result}



@route('/api/v1/contact_request', method = 'POST')
def contact_request():
    try:
        ipv6 = pad_ipv6(get_real_ip())
        what = request.POST.get('what', False)
        comments = request.POST.get('comments', '')

        if what == 'new':
            log.debug('receiving new request from %s', ipv6)
            data.db.get_profile(ipv6)
            data.db.addr_add_request('from', ipv6, comments)
            log.debug('done')
        elif what == 'confirm':
            log.debug('receiving confirmation from %s', + ipv6)
            data.db.addr_remove_request('to', ipv6)
            log.debug('done')
        elif what == 'decline':
            log.debug('receiving declination from %s', + ipv6)
            data.db.addr_remove_request('to', ipv6)
            log.debug('done')
        else:
            raise

        result = 'success'

    except Exception as strerr:
        log.error(strerr)
        result = 'failed'

    return {"result": result}
