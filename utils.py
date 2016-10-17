#!/usr/bin/python

from bottle import request, html_escape
from time import mktime, timezone
from re import compile as re_compile
import logging as log
import arrow

################################################################################
# utils
################################################################################

""" if you are on an ipv6, disallow access
(assume you are external, tun0)"""
def internal(fn):
    def check_ip(**kwargs):
        remote_ip = get_real_ip()

        if ':' in remote_ip:
            #return '404'
            # TODO: define your ipv6 and check that
            pass
        return fn(**kwargs)

    return check_ip

def get_real_ip():
    try:
        remote_ip = request.environ['HTTP_X_FORWARDED_FOR']
    except Exception:
        try:
            remote_ip = request.environ['HTTP_X_REAL_IP']
        except Exception:
            remote_ip = '::1'
    return remote_ip

def pad_ipv6(ipv6):
    splitter = ipv6.strip().split(':')
    return ':'.join([ str(block).zfill(4) for block in splitter ])

def format_datestring(date, pubdate_format=False):
    if pubdate_format:
        return arrow.get(date).format('ddd, DD MMM YYYY HH:MM:SS Z')
    return arrow.get(date).to('Europe/Zurich').format('HH:MM - DD. MMMM YYYY')

def format_text(text):
    text = html_escape(text)
    text = text.replace('\n', '<br />\n')
    r = re_compile(r"(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)")
    text = r.sub('<a target="_blank" href="\\1">\\1</a>', text)
    return text

def link_mentions(text, mentions):
    for m in mentions:
        for name, ipv6 in m.iteritems():
            text = text.replace('@' + name, '<a target="_blank" href="/' + ipv6 + '">@' + name + '</a>')
    return text

def one_hour_ago():
    return arrow.utcnow().replace(hours=-1)

TIME_FORMAT = 'YYYY-MM-DD HH:mm:ss.SSSSSS'
