#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
module for url manager
'''

import hashlib
import logging
import re
import time

import markdown2

from models import User, Blog, Comment
from config import configs
from transwarp.web import ctx, get, post, Page, api, view, interceptor
from transwarp.web import seeothererror, notfounderror, APIError, APIValueError, APIResourceNotFoundError, APIPermissionError

# cookie handler

_COOKIE_NAME = 'awesession'
_COOKIE_KEY = configs.session.secret

def _make_signed_cookie(id, password, max_age):
    # build cookie string by: id-expires-md5
    expires = str(int(time.time() + (max_age or 86400)))
    L = [ id, expires, hashlib.md5('%s-%s-%s-%s' % (id, password, expires, _COOKIE_KEY)).hexdigest() ]
    return '-'.join(L)

def _parse_signed_cookie(cookie_str):
    try:
        L = cookie_str.split('-')
        if len(L) != 3:
            return None
        user_id, expires, md5 = L
        if int(expires) < time.time():
            return None
        user = User.get(user_id)
        if user is None:
            return None
        if md5 != hashlib.md5('%s-%s-%s-%s' % (user.id, user.password, expires, _COOKIE_KEY)).hexdigest():
            return None
        return user
    except:
        return None

# define pagination

def _get_page_index():
    page_index = 1
    try:
        page_index = int(ctx.request.get('page', '1'))
    except ValueError, e:
        pass
    return page_index

def _get_blog_by_page():
    total = Blog.count_all()
    page = Page(total, _get_page_index())
    blogs = Blog.find_by('order by created_at desc limit ?,?', page.offset, page.limit)
    return blogs, page

# interceptor

@interceptor('/')
def user_interceptor(next):
    logging.info('[APP] [try to bind user from session cookie...]')
    user = None
    cookie = ctx.request.cookies.get(_COOKIE_NAME)
    if cookie:
        logging.info('[APP] [parse session cookie...]')
        user = _parse_signed_cookie(cookie)
        if user:
            logging.info('[APP] [success to bind user <%s> to session]' % user.email)
    ctx.request.user = user
    return next()

@interceptor('/manage/')
def manage_interceptor(next):
    user = ctx.request.user
    if user and user.admin:
        return next()
    raise seeothererror('/user/signin')

# view

def _check_admin():
    user = ctx.request.user
    if user and user.admin:
        return
    raise APIPermissionError('No Permission.')

@view('index.html')
@get('/')
def index():
    total = Blog.count_all()
    page = Page(total, _get_page_index())
    blogs = Blog.find_by('order by created_at desc limit ?,?', page.offset, page.limit)
    return dict(page=page, blogs=blogs, user=ctx.request.user)

@view('blog.html')
@get('/blog/:blog_id')
def blog(blog_id):
    blog = Blog.get(blog_id)
    if blog is None:
        raise notfounderror()
    blog.html_content = markdown2.markdown(blog.content)
    comments = Comment.find_by('where blog_id=? order by created_at desc limit 100', blog.id)
    return dict(blog=blog, comments=comments, user=ctx.request.user)

@view('signin.html')
@get('/signin')
def user_signin():
    return dict()

@get('/signout')
def user_signout():
    ctx.response.delete_cookie(_COOKIE_NAME)
    raise seeothererror('/')

@view('register.html')
@get('/register')
def user_register():
    return dict()

@get('/manage/')
def manage():
    raise seeothererror('/manage/comment/list')

@view('manage_user_list.html')
@get('/manage/user/list')
def manage_user_list():
    return dict(page_index=_get_page_index(), user=ctx.request.user)

@view('manage_blog_list.html')
@get('/manage/blog/list')
def manage_blog_list():
    return dict(page_index=_get_page_index(), user=ctx.request.user)

@view('manage_blog_edit.html')
@get('/manage/blog/create')
def manage_blog_create():
    return dict(blog_id=None, action='/api/blog/create', redirect="/manage/blog/list", user=ctx.request.user)

@view('manage_blog_edit.html')
@get('/manage/blog/update/:blog_id')
def manage_blog_update(blog_id):
    blog = Blog.get(blog_id)
    if blog is None:
        raise notfounderror()
    return dict(blog_id=blog.id, action='/api/blog/update/%s' % blog.id, redirect='/manage/blog/list', user=ctx.request.user)

@view('manage_comment_list.html')
@get('/manage/comment/list')
def manage_comment_list():
    return dict(page_index=_get_page_index(), user=ctx.request.user)

@api
@post('/api/user/authenticate')
def api_user_authenticate():
    i = ctx.request.input(email='', password='', remember='')
    email = i.email.strip().lower()
    password = i.password
    remember = i.remember
    user = User.find_first('where email=?', email)
    if user is None:
        raise APIError('auth:failed', 'email', 'Invalid email.')
    elif user.password != password:
        raise APIError('auth:failed', 'password', 'Invalid password.')
    # make session cookie
    max_age = 604800 if remember == 'true' else None
    cookie = _make_signed_cookie(user.id, user.password, max_age)
    ctx.response.set_cookie(_COOKIE_NAME, cookie, max_age=max_age)
    user.password = '******'
    return user

_RE_EMAIL = re.compile(r'^[a-z0-9\.\-\_]+\@[a-z0-9\-\_]+(\.[a-z0-9\-\_]+){1,4}$')
_RE_MD5 = re.compile(r'^[0-9a-f]{32}$')

@api
@post('/api/user/create')
def api_user_create():
    logging.info('[APP] [try to create a user...]')
    i = ctx.request.input(name='', email='', password='')
    name = i.name.strip()
    email = i.email.strip().lower()
    password = i.password
    if not name:
        raise APIValueError('name')
    if not email or not _RE_EMAIL.match(email):
        raise APIValueError('email')
    if not password or not _RE_MD5.match(password):
        raise APIValueError('password')
    user = User.find_first('where email=?', email)
    if user:
        raise APIError('register:failed', 'email', 'Email is already in use.')
    user = User(name=name, email=email, password=password, image='http://www.gravatar.com/avatar/%s?d=mm&s=120' % hashlib.md5(email).hexdigest())
    user.insert()
    # make session cookie:
    cookie = _make_signed_cookie(user.id, user.password, None)
    ctx.response.set_cookie(_COOKIE_NAME, cookie)
    logging.info('[APP] [create a user ok]')
    return user

@api
@get('/api/user/list')
def api_user_list():
    total = User.count_all()
    page = Page(total, _get_page_index())
    users = User.find_by('order by created_at desc limit ?,?', page.offset, page.limit)
    for u in users:
        u.password = '******'
    return dict(users=users, page=page)

@api
@get('/api/blog/:blog_id')
def api_blog(blog_id):
    blog = Blog.get(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    return blog

@api
@get('/api/blog/list')
def api_blog_list():
    format = ctx.request.get('format', '')
    total = Blog.count_all()
    page = Page(total, _get_page_index())
    blogs = Blog.find_by('order by created_at desc limit ?,?', page.offset, page.limit)
    if format == 'html':
        for blog in blogs:
            blog.content = markdown2.markdown(blog.content)
    return dict(blogs=blogs, page=page)

@api
@post('/api/blog/create')
def api_blog_create():
    logging.info('[APP] [try to create a blog...]')
    _check_admin()
    i = ctx.request.input(title='', summary='', content='')
    title = i.title.strip()
    summary = i.summary.strip()
    content = i.content.strip()
    if not title:
        raise APIValueError('title', 'title cannot be empty.')
    if not summary:
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content:
        raise APIValueError('content', 'content cannot be empty.')
    user = ctx.request.user
    blog = Blog(user_id=user.id, user_name=user.name, title=title, summary=summary, content=content)
    blog.insert()
    logging.info('[APP] [create a blog ok]')
    return blog

@api
@post('/api/blog/update/:blog_id')
def api_blog_update(blog_id):
    logging.info('[APP] [try to update a blog...]')
    _check_admin()
    i = ctx.request.input(title='', summary='', content='')
    title = i.title.strip()
    summary = i.summary.strip()
    content = i.content.strip()
    if not title:
        raise APIValueError('name', 'name cannot be empty.')
    if not summary:
        raise APIValueError('summary', 'summary cannot be empty.')
    if not content:
        raise APIValueError('content', 'content cannot be empty.')
    blog = Blog.get(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    blog.title = title
    blog.summary = summary
    blog.content = content
    blog.update()
    logging.info('[APP] [update a blog ok]')
    return blog

@api
@post('/api/blog/delete/:blog_id')
def api_blog_delete(blog_id):
    logging.info('[APP] [try to delete a blog...]')
    _check_admin()
    blog = Blog.get(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    blog.delete()
    logging.info('[APP] [delete a blog ok]')
    return None

@api
@get('/api/comment/list')
def api_comment_list():
    total = Comment.count_all()
    page = Page(total, _get_page_index())
    comments = Comment.find_by('order by created_at desc limit ?,?', page.offset, page.limit)
    return dict(comments=comments, page=page)

@api
@post('/api/comment/create/:blog_id')
def api_comment_create(blog_id):
    logging.info('[APP] [try to create a comment...]')
    user = ctx.request.user
    if user is None:
        raise APIPermissionError('Need signin.')
    blog = Blog.get(blog_id)
    if blog is None:
        raise APIResourceNotFoundError('Blog')
    content = ctx.request.input(content='').content.strip()
    if not content:
        raise APIValueError('content')
    comment = Comment(blog_id=blog.id, user_id=user.id, user_name=user.name, user_image=user.image, content=content)
    comment.insert()
    logging.info('[APP] [create a comment ok]')
    return dict(comment=comment)

@api
@post('/api/comment/delete/:comment_id')
def api_comment_delete(comment_id):
    logging.info('[APP] [try to delete a comment...]')
    _check_admin()
    comment = Comment.get(comment_id)
    if comment is None:
        raise notfounderror()
    comment.delete()
    logging.info('[APP] [delete a comment ok]')
    return dict(id=comment_id)

