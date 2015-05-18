#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
module for database operation
'''

import functools
import logging
import threading
import time
import uuid

from tool import SimpleDict

def generate_id(t=None):
    '''
    generate id as 50-char string
    '''
    if t is None:
        t = time.time()
    return '%015d%s000' % (int(t * 1000), uuid.uuid4().hex)

class DBError(Exception):
    pass

class MultiColumnsError(DBError):
    pass

# define database engine

_engine = None

class _Engine(object):
    
    def __init__(self, connect):
        self._connect = connect
    
    def connect(self):
        return self._connect()

def create_engine(user, password, database, host='127.0.0.1', port=3306, **kw):
    import mysql.connector
    global _engine
    if _engine is not None:
        raise DBError('Engine is already initialized.')
    params = dict(user=user, password=password, database=database, host=host, port=port)
    defaults = dict(use_unicode=True, charset='utf8', collation='utf8_general_ci', autocommit=True)
    for k, v in defaults.iteritems():
        params[k] = kw.pop(k, v)
    params.update(kw)
    params['buffered'] = True
    _engine = _Engine(lambda: mysql.connector.connect(**params))
    # test connection...
    logging.info('[DB] [init MySQL database engine <%s> ok.]' % hex(id(_engine)))

# define database context

class _LasyConnection(object):
    
    def __init__(self):
        self.connection = None
    
    def cursor(self):
        if self.connection is None:
            _connection = _engine.connect()
            logging.info('[DB] [open connection <%s>...]' % hex(id(_connection)))
            self.connection = _connection
        return self.connection.cursor()
    
    def commit(self):
        self.connection.commit()
    
    def rollback(self):
        self.connection.rollback()
    
    def cleanup(self):
        if self.connection:
            _connection = self.connection
            self.connection = None
            logging.info('[DB] [close connection <%s>...]' % hex(id(_connection)))
            _connection.close()
            
class _DatabaseContext(threading.local):
    '''
    threading.local object, hold connection info
    '''
    def __init__(self):
        self.connection = None
        self.transactions = 0
    
    def is_init(self):
        return not self.connection is None
    
    def init(self):
        logging.info('[DB] [open lasy connection...]')
        self.connection = _LasyConnection()
        self.transactions = 0
    
    def cursor(self):
        return self.connection.cursor()
    
    def cleanup(self):
        self.connection.cleanup()
        self.connection = None

_dbctx =_DatabaseContext()

# define connection context

class _ConnectionContext(object):
    '''
    open and close connection context
    '''
    def __enter__(self):
        global _dbctx
        self.should_cleanup = False
        if not _dbctx.is_init():
            _dbctx.init()
            self.should_cleanup = True
        return self
    
    def __exit__(self, exctype, excvalue, traceback):
        global _dbctx
        if self.should_cleanup:
            _dbctx.cleanup()

def connection():
    '''
    get _ConnectionContext object, used by 'with' statement
    
    with connection():
        pass
    '''
    return _ConnectionContext()

def with_connection(func):
    '''
    decorator for reuse connection
    
    @with_connection
    def foo(*args, **kw):
        f1()
        f2()
        f3()
    '''
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        with connection():
            return func(*args, **kw)
    return _wrapper

# define transaction context

class _TransactionContext(object):
    
    def __enter__(self):
        global _dbctx
        self.should_close_conn = False
        if not _dbctx.is_init():
            _dbctx.init()
            self.should_close_conn = True
        _dbctx.transactions = _dbctx.transactions + 1
        logging.info('[DB] [Transaction] [begin...]' if _dbctx.transactions == 1 else '[DB] [join current transaction...]')
        return self
    
    def commit(self):
        global _dbctx
        logging.info('[DB] [Transaction] [commit...]')
        try:
            _dbctx.connection.commit()
            logging.info('[DB] [Transaction] [commit ok.]')
        except:
            logging.warning('[DB] [Transaction] [commit failed, try rollback...]')
            _dbctx.connection.rollback()
            logging.warning('[DB] [Transaction] [rollback ok.]')
            raise
    
    def rollback(self):
        global _dbctx
        logging.warning('[DB] [Transaction] [rollback...]')
        _dbctx.connection.rollback()
        logging.info('[DB] [Transaction] [rollback ok]')
    
    def __exit__(self, exctype, excvalue, traceback):
        global _dbctx
        _dbctx.transactions = _dbctx.transactions - 1
        try:
            if _dbctx.transactions == 0:
                if exctype is None:
                    self.commit()
                else:
                    self.rollback()
        finally:
            if self.should_close_conn:
                _dbctx.cleanup()

def transaction():
    '''
    get _TransactionContext object, use by 'with' statement
    
    with transaction():
        pass
    
    >>> def update_profile(id, name, rollback):
    ...     u = dict(id=id, name=name, email='%s@test.org' % name, password=name, last_modified=time.time())
    ...     insert('user', **u)
    ...     r = update('update user set password=? where id=?', name.upper(), id)
    ...     if rollback:
    ...         raise StandardError('will cause rollback...')
    >>> with transaction():
    ...     update_profile(900301, 'Python', False)
    >>> select_one('select * from user where id=?', 900301).name
    u'Python'
    >>> with transaction():
    ...     update_profile(900302, 'Ruby', True)
    Traceback (most recent call last):
      ...
    StandardError: will cause rollback...
    >>> select('select * from user where id=?', 900302)
    []
    '''
    return _TransactionContext()

def with_transaction(func):
    @functools.wraps(func)
    def _wrapper(*args, **kw):
        _st = time.time()
        with transaction():
            return func(*args, **kw)
        _ut = time.time() - _st
        if _ut > 0.1:
            logging.warning('[DB] [Transaction] [%s]' % _ut)
    return _wrapper

# define SQL operation

def _profiling(st, sql='', *args):
    ut = time.time() - st
    if ut > 0.1:
        logging.warning('[DB] [%s] [SQL] [%s] [%s]' % (ut, sql, args))
    else:
        logging.info('[DB] [SQL] [%s] [%s]' % (sql, args))

@with_connection
def _select(sql, first, *args):
    global _dbctx
    cursor = None
    rtnVal = None
    sql = sql.replace('?', '%s')
    try:
        _st = time.time()
        cursor = _dbctx.connection.cursor()
        cursor.execute(sql, args)
        if cursor.description:
            names = [ x[0] for x in cursor.description ]
        if first:
            # get only one result
            values = cursor.fetchone()
            if values:
                rtnVal = SimpleDict(names, values)
        else:
            values = cursor.fetchall()
            rtnVal = [ SimpleDict(names, x) for x in values ]
        _profiling(_st, sql, *args)
        return rtnVal
    finally:
        if cursor:
            cursor.close()

def select_one(sql, *args):
    '''
    execute select SQL, expected only one result.
    
    >>> u1 = SimpleDict(id=100, name='Alice', email='alice@test.org', password='ABC-12345', last_modified=time.time())
    >>> u2 = SimpleDict(id=101, name='Sarah', email='sarah@test.org', password='ABC-12345', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> insert('user', **u2)
    1
    >>> u = select_one('select * from user where id=?', 100)
    >>> u.name
    u'Alice'
    >>> select_one('select * from user where email=?', 'abc@email.com')
    >>> u2 = select_one('select * from user where password=? order by email', 'ABC-12345')
    >>> u2.name
    u'Alice'
    '''
    return _select(sql, True, *args)

def select_int(sql, *args):
    '''
    execute select SQL, expected one int result. 
    
    >>> n = update('delete from user')
    >>> u1 = SimpleDict(id=96900, name='Ada', email='ada@test.org', password='A-12345', last_modified=time.time())
    >>> u2 = SimpleDict(id=96901, name='Adam', email='adam@test.org', password='A-12345', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> insert('user', **u2)
    1
    >>> select_int('select count(*) from user')
    2
    >>> select_int('select count(*) from user where email=?', 'ada@test.org')
    1
    >>> select_int('select count(*) from user where email=?', 'notexist@test.org')
    0
    >>> select_int('select id from user where email=?', 'ada@test.org')
    96900
    >>> select_int('select id, name from user where email=?', 'ada@test.org')
    Traceback (most recent call last):
        ...
    MultiColumnsError: Expect only one column.
    '''
    d = _select(sql, True, *args)
    if len(d) != 1:
        raise MultiColumnsError('Expect only one column.')
    return d.values()[0]

def select(sql, *args):
    '''
    execute select SQL
    
    >>> u1 = SimpleDict(id=200, name='Wall.E', email='wall.e@test.org', password='back-to-earth', last_modified=time.time())
    >>> u2 = SimpleDict(id=201, name='Eva', email='eva@test.org', password='back-to-earth', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> insert('user', **u2)
    1
    >>> L = select('select * from user where id=?', 900900900)
    >>> L
    []
    >>> L = select('select * from user where id=?', 200)
    >>> L[0].email
    u'wall.e@test.org'
    >>> L = select('select * from user where password=? order by id desc', 'back-to-earth')
    >>> L[0].name
    u'Eva'
    >>> L[1].name
    u'Wall.E'
    '''
    return _select(sql, False, *args)

@with_connection
def _update(sql, *args):
    global _dbctx
    cursor = None
    rtnVal = None
    sql = sql.replace('?', '%s')
#    logging.info('SQL: %s, ARGS: %s' % (sql, args))
    try:
        _st = time.time()
        cursor = _dbctx.connection.cursor()
        cursor.execute(sql, args)
        rtnVal = cursor.rowcount
        if _dbctx.transactions == 0:
            # no transaction environment
            logging.info('[DB] [auto commit]')
            _dbctx.connection.commit()
        _profiling(_st, sql, *args)
        return rtnVal
    finally:
        if cursor:
            cursor.close()

def insert(table, **kw):
    '''
    execute insert SQL
    
    >>> u1 = SimpleDict(id=2000, name='Bob', email='bob@test.org', password='bobobob', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> u2 = select_one('select * from user where id=?', 2000)
    >>> u2.name
    u'Bob'
    >>> insert('user', **u2)
    Traceback (most recent call last):
      ...
    IntegrityError: 1062 (23000): Duplicate entry '2000' for key 'PRIMARY'
    '''
    cols, args = zip(*kw.iteritems())
    sql = 'insert into `%s` (%s) values (%s)' % (table, ','.join([ '`%s`' % col for col in cols ]), ','.join([ '?' for i in range(len(args)) ]))
    return _update(sql, *args)

def update(sql, *args):
    '''
    execute update/delete SQL
    
    >>> u1 = SimpleDict(id=1000, name='Michael', email='michael@test.org', password='123456', last_modified=time.time())
    >>> insert('user', **u1)
    1
    >>> u2 = select_one('select * from user where id=?', 1000)
    >>> u2.email
    u'michael@test.org'
    >>> u2.password
    u'123456'
    >>> update('update user set email=?, password=? where id=?', 'michael@example.org', '654321', 1000)
    1
    >>> u3 = select_one('select * from user where id=?', 1000)
    >>> u3.email
    u'michael@example.org'
    >>> u3.password
    u'654321'
    >>> update('update user set password=? where id=?', '***', "123\' or id=\'456")
    0
    '''
    return _update(sql, *args)

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    create_engine('www-data', 'www-data', 'test')
    update('drop table if exists user')
    update('create table user (id int primary key, name text, email text, password text, last_modified real)')
    import doctest
    doctest.testmod()
