#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
module for app data models
'''

import time

from transwarp.db import generate_id
from transwarp.orm import Model, StringField, BooleanField, FloatField, TextField


class User(Model):
    __table__ = 'users'
    
    id = StringField(primary_key=True, default=generate_id, ddl='varchar(50)')
    email = StringField(updatable=False, ddl='varchar(50)')
    password = StringField(ddl='varchar(50)')
    admin = BooleanField()
    name = StringField(ddl='varchar(50)')
    image= StringField(ddl='varchar(500)')
    created_at = FloatField(updatable=False, default=time.time)

class Blog(Model):
    __table__ = 'blogs'
    
    id = StringField(primary_key=True, default=generate_id, ddl='varchar(50)')
    user_id = StringField(updatable=False, ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image= StringField(ddl='varchar(500)')
    title = StringField(ddl='varchar(50)')
    summary = StringField(ddl='varchar(200)')
    content = TextField()
    created_at = FloatField(updatable=False, default=time.time)

class Comment(Model):
    __table__ = 'comments'
    
    id = StringField(primary_key=True, default=generate_id, ddl='varchar(50)')
    blog_id = StringField(updatable=False, ddl='varchar(50)')
    user_id = StringField(updatable=False, ddl='varchar(50)')
    user_name = StringField(ddl='varchar(50)')
    user_image= StringField(ddl='varchar(500)')
    content = TextField()
    created_at = FloatField(updatable=False, default=time.time)

if __name__ == '__main__':
    from transwarp.db import create_engine
    create_engine(user='www-data', password='www-data', database='awesome')
    u1 = User(name='Test', email='test@example.com', password='1234567890', image='about:blank')
    u1.insert()
    print 'new user id:', u1.id
    u2 = User.get(u1.id)
    print 'find user:', u2
    u2.delete()
    u3 = User.find_first('where email=?', 'test@example.com')
    print 'find user:', u3
