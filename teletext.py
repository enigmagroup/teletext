#!/usr/bin/python

from gevent import spawn, sleep, monkey; monkey.patch_all()
from bottle import run, debug
import logging
logging.basicConfig(
    format = "%(levelname) -10s %(asctime)s %(module)s.py:%(lineno)s %(funcName)s(): %(message)s",
    level=logging.INFO
)

from routes import *
from workers import *



# spawn the write worker
spawn(write_worker)

# spawn 10 notification workers with some delay in between to prevent segfaults
for i in range(10):
    spawn(notification_worker)
    sleep(0.2)



if __name__ == "__main__":
    debug(True)
    run(host='127.0.0.1', port=8008, server='gevent')

app = default_app()
