#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
module for wsgi application
'''

from datetime import datetime
import os
import time

import logging
#logging.basicConfig(level=logging.WARNING)
logging.basicConfig(level=logging.INFO)

from transwarp import db
from transwarp.web import WSGIApplication, Jinja2TemplateEngine
from config import configs

def datetime_filter(t):
    delta = int(time.time() - t)
    if delta < 60:
        return u'1分钟前'
    if delta < 3600:
        return u'%s分钟前' % (delta // 60)
    if delta < 86400:
        return u'%s小时前' % (delta // 3600)
    if delta < 604800:
        return u'%s天前' % (delta // 86400)
    dt = datetime.fromtimestamp(t)
    return u'%s年%s月%s日' % (dt.year, dt.month, dt.day)

# inin database
db.create_engine(**configs.db)

# init template engine
template_engine = Jinja2TemplateEngine(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates'))
template_engine.add_filter('datetime', datetime_filter)

# init wsgi application
wsgi = WSGIApplication(os.path.dirname(os.path.abspath(__file__)))
wsgi.template_engine = template_engine

# add url module to wsgi
import urls
wsgi.add_interceptor(urls.user_interceptor)
wsgi.add_interceptor(urls.manage_interceptor)
wsgi.add_module(urls)

# run application
if __name__ == '__main__':
    wsgi.run()
else:
    application = wsgi.get_wsgi_application()
