all:
	clear
	#./teletext.py
	#sudo -u www-data gunicorn --bind=127.0.0.1:8008 --worker-class=gevent_pywsgi --workers=1 --debug --log-level=debug teletext:app
	coffee -c -b --no-header -o public/js/ public/js/src/
	cat public/js/init.js > public/js/default.min.js
	cat public/js/t.*.js >> public/js/default.min.js
	gunicorn --bind=127.0.0.1:8008 --worker-class=gevent_pywsgi --workers=1 --log-level=debug teletext:app

.PHONY: all
