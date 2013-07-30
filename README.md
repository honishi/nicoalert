nicoalert
=============
![anokoku](https://dl.dropboxusercontent.com/u/444711/github.com/honishi/nicoalert/ankoku.jpeg)

niconama alert for twitter

sample
-------------
![tweets](https://dl.dropboxusercontent.com/u/444711/github.com/honishi/nicoalert/tweets.png)

required library
-------------
1. `sudo apt-get install libxml2-dev`
2. `sudo apt-get install libxslt1-dev`

setup
-------------
1. `git submodule update --init`
2. `virtualenv --distribute venv`
3. `source ./venv/bin/activate`
4. `pip install -r requirements.txt`
5. `copy nicoalert.config.sample nicoalert.config` then edit
6. `./nicoalert.sh start` and `./nicoalert.sh stop`

monitoring example using crontab
-------------

	# monitoring nicoalert
	* * * * * /path/to/nicoalert/nicoalert.sh monitor >> /path/to/nicoalert/log/monitor.log 2>&1

license
-------------

copyright &copy; 2012- honishi, hiroyuki onishi.

distributed under the [MIT license][mit].
[mit]: http://www.opensource.org/licenses/mit-license.php
