#!/usr/bin/python

from gevent import spawn, monkey; monkey.patch_all()
from bottle import route, error, static_file, template, request, abort, redirect, debug
from urllib import quote
from urllib2 import urlopen
from datetime import datetime
from json import loads as json_loads, dumps as json_dumps

from api import *
from utils import *
from data import *
from workers import *

################################################################################
# routes
################################################################################

@route('/')
@internal
def root():
    username = data.get_meta('username', '')
    if username == '':
        redirect('/settings')

    check_new_transmissions()
    telegrams = data.get_telegrams()

    return template('home',
        telegrams = telegrams,
        xhr_url = '/xhr/timeline',
        rss_url = '/rss',
        my_ipv6 = data.get_meta('ipv6'),
        pending_requests = data.pending_requests_exist(),
    )



@route('/rss')
@internal
def rss():
    username = data.get_meta('username', '')
    if username == '':
        redirect('/settings')

    check_new_transmissions()
    telegrams = data.get_telegrams()

    return template('rss',
        telegrams = telegrams,
        rss_url = '/rss',
        author = '',
    )



@route('/new_telegram', method = 'POST')
@internal
def new_telegram():
    text = request.POST.get('telegram', '').strip()

    if text != '':
        text = text.decode('utf-8')
        ipv6 = data.get_meta('ipv6')
        now = str(datetime.utcnow())

        queue = Queue()

        json = {
            'job_desc': 'add_telegram',
            'telegram': {
                'text': text,
                'author': ipv6,
                'created_at': now,
                'imported': 0,
            }
        }

        json = json_dumps(json)
        queue.add('write', json, 1)
        log.debug('write-job added to queue: %s', json)

        json = {
            'job_desc': 'notify_all_subscribers',
            'telegram': {
                'text': text,
                'created_at': now,
            }
        }

        json = json_dumps(json)
        queue.add('notification', json)
        log.debug('notification-job added to queue: %s', json)

        queue.close()

    redirect('/')



@route('/<ipv6:re:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}>')
@internal
def profile_page(ipv6):
    username = data.get_meta('username', '')
    if username == '':
        redirect('/settings')

    my_ipv6 = data.get_meta('ipv6')
    profile = data.get_profile(ipv6)
    telegrams = data.get_telegrams(author = ipv6, fetch_external = True)
    subscribed = data.is_in_subscriptions(ipv6)

    return template('me',
        template = 'timeline',
        telegrams = telegrams,
        xhr_url = '/xhr/timeline?ipv6=' + ipv6,
        rss_url = '/' + ipv6 + '/rss',
        ipv6 = ipv6,
        username = profile['name'],
        bio = profile['bio'],
        transmissions = profile['transmissions'],
        subscribers = profile['subscribers'],
        subscriptions = profile['subscriptions'],
        my_ipv6 = my_ipv6,
        pending_requests = data.pending_requests_exist(),
        subscribed = subscribed,
    )



@route('/<ipv6:re:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}>/rss')
@internal
def profile_page_rss(ipv6):
    username = data.get_meta('username', '')
    if username == '':
        redirect('/settings')

    my_ipv6 = data.get_meta('ipv6')
    profile = data.get_profile(ipv6)
    telegrams = data.get_telegrams(author = ipv6, fetch_external = True)

    return template('rss',
        telegrams = telegrams,
        rss_url = '/' + ipv6 + '/rss',
        author = ' - ' + profile['name'],
    )



@route('/<ipv6:re:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}>/<subscription_type:re:(subscribers|subscriptions)>')
@internal
def me(ipv6, subscription_type):

    my_ipv6 = data.get_meta('ipv6')
    profile = data.get_profile(ipv6)
    user_list = data.get_userlist(subscription_type, ipv6 = ipv6)
    subscribed = data.is_in_subscriptions(ipv6)

    return template('me',
        template = 'user_list',
        user_list = user_list,
        xhr_url = '/xhr/user_list/' + ipv6 + '/' + subscription_type,
        ipv6 = ipv6,
        username = profile['name'],
        bio = profile['bio'],
        transmissions = profile['transmissions'],
        subscribers = profile['subscribers'],
        subscriptions = profile['subscriptions'],
        my_ipv6 = my_ipv6,
        pending_requests = data.pending_requests_exist(),
        subscribed = subscribed,
    )



@route('/<ipv6:re:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}>/<created_at>')
@internal
def single_telegram(ipv6, created_at):

    my_ipv6 = data.get_meta('ipv6')
    telegram = data.get_single_telegram(ipv6, created_at)

    if telegram == None:
        abort(404, 'Telegram does not exist')

    return template('telegram',
        telegram = telegram,
        my_ipv6 = my_ipv6,
        pending_requests = data.pending_requests_exist(),
    )



@route('/addressbook')
@internal
def addressbook():
    username = data.get_meta('username', '')
    if username == '':
        redirect('/settings')

    try:
        response = urlopen(url='http://127.0.0.1:8000/api/v1/get_contacts', timeout = 5)
        content = response.read()
        user_list = json_loads(content)['value']
    except Exception:
        user_list = {}

    for i, user in enumerate(user_list):
        ipv6 = pad_ipv6(user_list[i]['ipv6'])
        user_list[i]['ipv6'] = ipv6
        user_list[i]['subscribed'] = data.is_in_subscriptions(ipv6)
        user_list[i]['name'] = user_list[i]['display_name']

    return template('addressbook',
        user_list = user_list,
        my_ipv6 = data.get_meta('ipv6'),
        pending_requests = data.pending_requests_exist(),
    )



@route('/addressbook/requests', method = ['GET', 'POST'])
@internal
def addressbook_requests():

    addrbook_url = ''

    if request.POST.get('confirm_request'):
        ipv6 = request.POST.get('confirm_request')
        profile = data.get_profile(ipv6)
        username = profile['name'].encode('utf-8')

        log.debug('making request to Enigmabox address book...')
        response = urlopen(url='http://127.0.0.1:8000/api/v1/add_contact',
            data = 'ipv6=' + ipv6 + '&hostname=' + quote(username),
            timeout = 5,
        )
        content = response.read()
        addrbook_url = json_loads(content)['addrbook_url']
        log.debug('making request to %s', ipv6)
        urlopen(url='http://[' + ipv6 + ']:3838/api/v1/contact_request',
            data = 'what=confirm',
            timeout = 5,
        )
        data.addr_remove_request('from', ipv6)
        log.debug('done.')

    if request.POST.get('decline_request'):
        ipv6 = request.POST.get('decline_request')
        log.debug('making request to %s', ipv6)
        urlopen(url='http://[' + ipv6 + ']:3838/api/v1/contact_request',
            data = 'what=decline',
            timeout = 5,
        )
        data.addr_remove_request('from', ipv6)
        log.debug('done.')

    requests_list = data.addr_get_requests('from')

    return template('addressbook_requests',
        requests_list = requests_list,
        addrbook_url = addrbook_url,
        my_ipv6 = data.get_meta('ipv6'),
        pending_requests = data.pending_requests_exist(),
    )



@route('/addressbook/requests/<ipv6:re:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}>', method = ['GET', 'POST'])
@internal
def addressbook_new_request(ipv6):

    addrbook_url = ''
    profile = data.get_profile(ipv6)
    username = profile['name'].encode('utf-8')
    comments = request.POST.get('comments', '')[:256]

    if request.POST.get('send_request') and ipv6 != '':
        log.debug('making request to Enigmabox address book...')
        response = urlopen(url='http://127.0.0.1:8000/api/v1/add_contact',
            data = 'ipv6=' + ipv6 + '&hostname=' + quote(username),
            timeout = 5,
        )
        content = response.read()
        addrbook_url = json_loads(content)['addrbook_url']
        log.debug('making request to %s', ipv6)
        urlopen(url='http://[' + ipv6 + ']:3838/api/v1/contact_request',
            data = 'what=new&comments=' + quote(comments),
            timeout = 5,
        )
        data.addr_add_request('to', ipv6, comments)
        log.debug('done.')
        message = 'Request sent.'

    return template('addressbook_new_request',
        ipv6 = ipv6,
        addrbook_url = addrbook_url,
        my_ipv6 = data.get_meta('ipv6'),
        pending_requests = data.pending_requests_exist(),
    )



@route('/settings', method = ['GET', 'POST'])
@internal
def settings():

    ipv6 = data.get_meta('ipv6', False)

    if not ipv6:
        try:
            response = urlopen(url='http://127.0.0.1:8000/api/v1/get_option',
                data = 'key=ipv6',
                timeout = 5,
            )
            content = response.read()
            ipv6 = json_loads(content)['value'].strip()

        except Exception:
            ipv6 = '0000:0000:0000:0000:0000:0000:0000:0000' #TODO

    user_id = data._get_or_create_userid(ipv6)
    data.set_meta('ipv6', ipv6)

    message = ('', '')

    # prefetch all profiles from the address book in the background
    try:
        response = urlopen(url='http://127.0.0.1:8000/api/v1/get_contacts', timeout = 5)
        content = response.read()
        user_list = json_loads(content)['value']
        for u in user_list:
            spawn(data.get_profile, u['ipv6'])
    except Exception:
        log.info('No Enigmabox address book found, ignoring...')

    if request.POST.get('save'):
        username = request.POST.get('username', '')[:30].decode('utf-8')
        bio = request.POST.get('bio', '')[:256].decode('utf-8')
        show_subscribers = request.POST.get('show_subscribers', '0')
        show_subscriptions = request.POST.get('show_subscriptions', '0')

        if username != '':
            data.set_meta('username', username)
            data.set_meta('bio', bio)
            data.set_meta('show_subscribers', show_subscribers)
            data.set_meta('show_subscriptions', show_subscriptions)

            image = request.files.get('image', False)

            if image:
                from PIL import Image
                img = Image.open(image.file)
                img.thumbnail((75, 75), Image.ANTIALIAS)
                img.save('./public/img/profile/' + ipv6 + '.png')

            data.set_user_attr(user_id, 'name', username)
            data.set_user_attr(user_id, 'bio', bio)

            message = ('success', 'Data successfully saved.')

        else:
            message = ('error', 'Error: Username must no be blank')

    return template('settings',
        username = data.get_meta('username', ''),
        bio = data.get_meta('bio', ''),
        show_subscribers = data.get_meta('show_subscribers', '1'),
        show_subscriptions = data.get_meta('show_subscriptions', '1'),
        message = message,
        my_ipv6 = data.get_meta('ipv6'),
        pending_requests = data.pending_requests_exist(),
    )



@route('/static/<filepath:path>')
@internal
def server_static(filepath):
    return static_file(filepath, root = './public')



@route('/xhr/timeline')
@internal
def xhr_timeline():

    step = request.GET.get('step', 0)
    since = request.GET.get('since', False)
    ipv6 = request.GET.get('ipv6', False)

    if ipv6:
        telegrams = data.get_telegrams(author = ipv6, step = step, since = since, fetch_external = True)
    else:
        telegrams = data.get_telegrams(step = step, since = since)

    return template('timeline',
        telegrams = telegrams,
        xhr = True,
        my_ipv6 = data.get_meta('ipv6'),
        pending_requests = data.pending_requests_exist(),
    )



@route('/xhr/user_list/<ipv6:re:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}:.{4}>/<subscription_type>')
@internal
def xhr_userlist(ipv6, subscription_type):

    step = request.GET.get('step', 0)
    user_list = data.get_userlist(subscription_type, ipv6, step)

    return template('user_list',
        user_list = user_list,
        xhr = True,
    )



@route('/xhr/subscribe', method = 'POST')
@internal
def xhr_subscribe():

    what = request.POST.get('what')
    ipv6 = request.POST.get('ipv6')

    if what == 'subscribe':
        try:
            response = urlopen(url='http://[' + ipv6 + ']:3838/api/v1/subscribe',
                data = 'ipv6=' + ipv6,
                timeout = 5,
            )
            content = response.read()
            result = json_loads(content)['result']
        except Exception:
            result = 'failed'

        if result == 'success':
            data.add_subscription(ipv6)

        return {"result": result}

    elif what == 'unsubscribe':
        try:
            # just send a notification, but don't care for the result
            # unsubscribed guys will be checked with the next push notification
            response = urlopen(url='http://[' + ipv6 + ']:3838/api/v1/unsubscribe',
                data = 'ipv6=' + ipv6,
                timeout = 5,
            )
        except Exception:
            pass

        data.remove_subscription(ipv6)
        return {"result": "success"}



@route('/xhr/retransmit', method = 'POST')
@internal
def xhr_retransmit():
    ipv6 = request.POST.get('ipv6')
    created_at = request.POST.get('created_at')

    queue = Queue()

    json = {
        'job_desc': 'retransmit_telegram',
        'telegram': {
            'ipv6': ipv6,
            'created_at': created_at,
        }
    }

    json = json_dumps(json)
    queue.add('write', json)

    # retransmit_telegram() handles the notification

    queue.close()

    return {"result": "success"}



@route('/xhr/delete', method = 'POST')
@internal
def xhr_delete():
    #ipv6 = request.POST.get('ipv6')
    my_ipv6 = data.get_meta('ipv6')
    created_at = request.POST.get('created_at')

    queue = Queue()

    json = {
        'job_desc': 'delete_telegram',
        'telegram': {
            'ipv6': my_ipv6,
            'created_at': created_at,
        }
    }

    json = json_dumps(json)
    queue.add('write', json)

    queue.close()

    return {"result": "success"}



@route('/xhr/check_status')
@internal
def xhr_check_status():
    ipv6 = request.GET.get('ipv6')
    try:
        response = urlopen(url='http://[' + ipv6 + ']:3838/api/v1/ping',
            timeout = 5,
        )
        content = response.read()
        result = json_loads(content)['result']
    except Exception:
        result = 'failed'

    return {"result": result}



@error(404)
def error404(error):
    return '404'

@error(405)
def error405(error):
    return '405'
