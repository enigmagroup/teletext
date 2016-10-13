#!/usr/bin/python

from bottle import request, html_escape
from datetime import datetime
from time import mktime
from re import compile as re_compile
import logging as log

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
    dt = datetime.strptime(date, '%Y-%m-%d %H:%M:%S.%f')
    if pubdate_format:
        return dt.strftime('%a, %d %b %Y %H:%M:%S %z')
    epoch = mktime(dt.timetuple())
    offset = datetime.fromtimestamp(epoch) - datetime.utcfromtimestamp(epoch)
    dt = dt + offset
    return dt.strftime('%H:%M - %d. %B %Y')

def format_text(text):
    text = html_escape(text)
    text = text.replace('\n', '<br />\n')
    r = re_compile(r"(http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+)")
    text = r.sub('<a target="_blank" href="\\1">\\1</a>', text)
    return text
