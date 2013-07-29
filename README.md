nicoalert
=============

niconama alert for twitter

how to use
-------------

first, install the following packages for lxml.

1. sudo apt-get install libxml2-dev
2. sudo apt-get install libxslt1-dev 

then, install nicoalert.

1. copy nicoalert.config.sample to nicoalert.config, then edit
2. copy twitter.config.sample to twitter.config, then edit
3. git submodule update --init
4. virtualenv --distribute venv
5. source ./venv/bin/activate
6. pip install -r requirements.txt
7. kick ./nicoalert start

example crontab
-------------

	# monitoring nicoalert
	* * * * * /path/to/nicoalert/nicoalert.sh monitor >> /path/to/nicoalert/log/monitor.log 2>&1

license
-------------

copyright &copy; 2012 honishi, hiroyuki onishi.

distributed under the [MIT license][mit].
[mit]: http://www.opensource.org/licenses/mit-license.php
