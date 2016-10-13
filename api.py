#!/usr/bin/python

from bottle import route, error, run, static_file, template, request, abort, redirect, debug, default_app, html_escape
from json import loads as json_loads, dumps as json_dumps

from data import *

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
    ipv6 = data.get_meta('ipv6')
    telegrams = data.get_telegrams(author = ipv6, no_imported = True, step = step, since = since)

    for key, val in enumerate(telegrams):
        telegrams[key]['text'] = telegrams[key]['text_unescaped']
        del(telegrams[key]['text_unescaped'])
        del(telegrams[key]['author'])
        del(telegrams[key]['ipv6'])
        del(telegrams[key]['created_at_formatted'])
        del(telegrams[key]['retransmission_from_author'])
        del(telegrams[key]['retransmission_original_time_formatted'])

        if telegrams[key]['retransmission_from'] == None:
            del(telegrams[key]['retransmission_from'])
            del(telegrams[key]['retransmission_original_time'])

    return {"telegrams": telegrams}



@route('/api/v1/get_single_telegram.json')
def single_telegram_json():
    my_ipv6 = data.get_meta('ipv6')
    created_at = request.GET.get('created_at')
    telegram = data.get_single_telegram(my_ipv6, created_at)

    if telegram:
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
            ipv6 = pad_ipv6(get_real_ip())
            created_at = telegram['created_at']

            if not data.is_in_subscriptions(ipv6):
                return {"result": "unsubscribed"}

            try:
                # retransmission

                retransmission_from = telegram['retransmission_from']
                retransmission_original_time = telegram['retransmission_original_time']

                if data.retransmission_exists(retransmission_from, retransmission_original_time):
                    return {"result": "failed"}

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

                queue = Queue()
                queue.add('write', json)
                queue.close()

                result = 'success'

            except Exception:
                # regular telegram

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

                queue = Queue()
                queue.add('write', json)
                queue.close()

                result = 'success'

        except Exception as strerr:
            log.error('Error adding telegram in api.py: %s', strerr)
            result = 'error'

    return {"result": result}



@route('/api/v1/get_profile.json')
def profile_json():
    my_ipv6 = data.get_meta('ipv6')
    profile = data.get_profile(my_ipv6)

    del(profile['ipv6'])
    del(profile['updated_at'])
    profile['bio'] = profile['bio_unescaped']
    del(profile['bio_unescaped'])

    return {"profile": profile}



@route('/avatar.png')
def external_profile_image():
    ipv6 = data.get_meta('ipv6')
    return static_file('/img/profile/' + ipv6 + '.png', root = './public')



@route('/api/v1/get_subscription.json')
def profile_json():

    subscription_type = request.GET.get('type')
    step = request.GET.get('step', 0)

    if subscription_type == 'subscribers':
        show_subscribers = data.get_meta('show_subscribers', '0')
        if show_subscribers == '1':
            user_list = data.get_userlist(subscription_type = 'subscribers', step = step),

    elif subscription_type == 'subscriptions':
        show_subscriptions = data.get_meta('show_subscriptions', '0')
        if show_subscriptions == '1':
            user_list = data.get_userlist(subscription_type = 'subscriptions', step = step),

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
        data.add_subscriber(ipv6)
        result = 'success'
    except Exception:
        result = 'failed'

    return {"result": result}



@route('/api/v1/unsubscribe', method = 'POST')
def external_unsubscribe():
    try:
        ipv6 = pad_ipv6(get_real_ip())
        data.remove_subscriber(ipv6)
        result = 'success'
    except Exception:
        result = 'failed'

    return {"result": result}



@route('/api/v1/contact_request', method = 'POST')
def contact_request():
    try:
        ipv6 = pad_ipv6(get_real_ip())
        what = request.POST.get('what', False)
        comments = request.POST.get('comments', '')

        if what == 'new':
            print 'receiving new request'
            data.get_profile(ipv6)
            data.addr_add_request('from', ipv6, comments)
            print 'done.'
        elif what == 'confirm':
            print 'receiving confirmation from ' + ipv6
            data.addr_remove_request('to', ipv6)
            print 'done.'
        elif what == 'decline':
            print 'receiving declination from ' + ipv6
            data.addr_remove_request('to', ipv6)
        else:
            raise

        result = 'success'

    except Exception:
        result = 'failed'

    return {"result": result}
