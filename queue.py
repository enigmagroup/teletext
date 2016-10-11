#!/usr/bin/python

import beanstalkc

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
