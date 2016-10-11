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

################################################################################
# queue class
################################################################################

class Queue():
    def __init__(self):
        self.bs = beanstalkc.Connection()

    def add(self, queue, value, priority=100):
        self.bs.use(queue)
        self.bs.put(value, priority=priority)

    def get_job(self, queue):
        self.bs.watch(queue)
        return self.bs.reserve()

    def close(self):
        self.bs.close()

