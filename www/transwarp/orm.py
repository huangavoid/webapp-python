#!/usr/bin/env python
# -*- coding: utf-8 -*-

'''
module for object-relationship mapping
'''

import logging

import db

class Field(object):
    
    _count = 0
    
    def __init__(self, **kw):
        self.name = kw.get('name', None)
        self.ddl = kw.get('ddl', '')
        self._default = kw.get('default', None)
        self.insertable = kw.get('insertable', True)
        self.updatable = kw.get('updatable', True)
        self.nullable = kw.get('nullable', False)
        self.primary_key = kw.get('primary_key', False)
        self._order = Field._count
        Field._count = Field._count + 1
    
    @property
    def default(self):
        d = self._default
        return d() if callable(d) else d
    
    def __str__(self):
        s = ['<%s:%s,%s,default(%s),' % (self.__class__.__name__, self.name, self.ddl, self._default)]
        self.insertable and s.append('I')
        self.updatable and s.append('U')
        self.nullable and s.append('N')
        s.append('>')
        return ''.join(s)

class BooleanField(Field):
    
    def __init__(self, **kw):
        if not 'ddl' in kw:
            kw['ddl'] = 'bool'
        if not 'default' in kw:
            kw['default'] = False
        super(BooleanField, self).__init__(**kw)

class IntegerField(Field):
    
    def __init__(self, **kw):
        if not 'ddl' in kw:
            kw['ddl'] = 'bigint'
        if not 'default' in kw:
            kw['default'] = 0
        super(IntegerField, self).__init__(**kw)

class FloatField(Field):
    
    def __init__(self, **kw):
        if not 'ddl' in kw:
            kw['ddl'] = 'real'
        if not 'default' in kw:
            kw['default'] = 0.0
        super(FloatField, self).__init__(**kw)

class StringField(Field):
    
    def __init__(self, **kw):
        if not 'ddl' in kw:
            kw['ddl'] = 'varchar(255)'
        if not 'default' in kw:
            kw['default'] = ''
        super(StringField, self).__init__(**kw)

class TextField(Field):
    
    def __init__(self, **kw):
        if not 'ddl' in kw:
            kw['ddl'] = 'text'
        if not 'default' in kw:
            kw['default'] = ''
        super(TextField, self).__init__(**kw)

class BlobField(Field):
    
    def __init__(self, **kw):
        if not 'ddl' in kw:
            kw['ddl'] = 'blob'
        if not 'default' in kw:
            kw['default'] = ''
        super(BlobField, self).__init__(**kw)

class VersionField(Field):
    
    def __init__(self, name=None):
        super(VersionField, self).__init__(name=name, ddl='bigint', default=0)

_triggers = frozenset(['pre_insert', 'pre_update', 'pre_delete'])

def _generate_table(table_name, mappings):
    _pk = ''
    sql = []
    sql.append('-- generate `%s` table' % table_name)
    sql.append('create table `%s` (' % table_name)
    for field in sorted(mappings.values(), lambda x, y: cmp(x._order, y._order)):
        if not hasattr(field, 'ddl'):
            raise StandardError("field '%s' has no ddl." % field)
        if field.primary_key:
            _pk = field.name
        sql.append(field.nullable and '    `%s` %s,' % (field.name, field.ddl) or '    `%s` %s not null,' % (field.name, field.ddl))
    if not _pk:
        raise StandardError("table '%s' has no pk." % field)
    sql.append('    primary key (`%s`)' % _pk)
    sql.append(');')
    return '\n'.join(sql)

class ModelMetaclass(type):
    '''
    metaclass for Model object
    '''
    def __new__(cls, name, bases, attrs):
        # skip base Model class
        if name == 'Model':
            return type.__new__(cls, name, bases, attrs)
        
        # subclass, store info
        if not hasattr(cls, 'subclasses'):
            cls.subclasses = {}
        if not name in cls.subclasses:
            cls.subclasses[name] = name
        else:
            logging.warning('[ORM] [redefine %s class]' % name)
        
        logging.info('[ORM] [scan %s class...]' % name)
        mappings = dict()
        _pk = None
        for k, v in attrs.iteritems():
            if isinstance(v, Field):
                if not v.name:
                    v.name = k
                # check primary key
                if v.primary_key:
                    # duplicate error
                    if _pk:
                        raise TypeError("Duplicate primary keys in class '%s'." % name)
                    if v.updatable:
                        logging.warning('[ORM] [NOTE: change primary key to non-updatable]') 
                        v.updatable = False
                    if v.updatable:
                        logging.warning('[ORM] [NOTE: change primary key to non-nullable]') 
                        v.nullable = False
                    _pk = v
                mappings[k] = v
                logging.info('[ORM] [found mapping: %s => %s]' % (k, v))
        
        # not defined primary key 
        if not _pk:
            raise TypeError("Not defined primary key in class '%s'.", name)
        
        for k in mappings.iterkeys():
            attrs.pop(k)
        if not '__table__' in attrs:
            attrs['__table__'] = name.lower()
        attrs['__mappings__'] = mappings
        attrs['__primary_key__'] = _pk
        attrs['__sql__'] = lambda self: _generate_table(attrs['__table__'], mappings)
        for trigger in _triggers:
            if not trigger in attrs:
                attrs[trigger] = None
        return type.__new__(cls, name, bases, attrs)

class Model(dict):
    '''
    Base class for ORM.
    
    >>> import time
    >>> class User(Model):
    ...     id = IntegerField(primary_key=True)
    ...     name = StringField()
    ...     email = StringField(updatable=False)
    ...     password = StringField(default=lambda: '******')
    ...     last_modified = FloatField()
    ...     def pre_insert(self):
    ...         self.last_modified = time.time()
    >>> u = User(id=10190, name='Michael', email='orm@db.org')
    >>> r = u.insert()
    >>> u.email
    'orm@db.org'
    >>> u.password
    '******'
    >>> u.last_modified > (time.time() - 2)
    True
    >>> f = User.get(10190)
    >>> f.name
    u'Michael'
    >>> f.email
    u'orm@db.org'
    >>> f.email = 'changed@db.org'
    >>> r = f.update() # change email but email is non-updatable!
    >>> len(User.find_all())
    1
    >>> g = User.get(10190)
    >>> g.email
    u'orm@db.org'
    >>> r = g.delete()
    >>> len(db.select('select * from user where id=10190'))
    0
    >>> import json
    >>> print User().__sql__()
    -- generate `user` table
    create table `user` (
        `id` bigint not null,
        `name` varchar(255) not null,
        `email` varchar(255) not null,
        `password` varchar(255) not null,
        `last_modified` real not null,
        primary key (`id`)
    );
    '''
    __metaclass__ = ModelMetaclass
    
    def __init__(self, **kw):
        super(Model, self).__init__(**kw)
    
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError, e:
            raise AttributeError(r"'Model' object has not attribute '%s'" % key)
    
    def __setattr__(self, key, value):
        self[key] = value
    
    @classmethod
    def get(cls, pk):
        '''
        'select' by pk, return one
        '''
        d = db.select_one('select * from `%s` where %s=?' % (cls.__table__, cls.__primary_key__.name), pk)
        return cls(**d) if d else None
    
    @classmethod
    def find_first(cls, where, *args):
        '''
        'select' with 'where', return one
        '''
        d = db.select_one('select * from %s %s' % (cls.__table__, where), *args)
        return cls(**d) if d else None
    
    @classmethod
    def find_all(cls, *args):
        '''
        'select', return all
        '''
        L = db.select('select * from `%s`' % cls.__table__)
        return [ cls(**d) for d in L ]
    
    @classmethod
    def find_by(cls, where, *args):
        '''
        'select' with 'where', return all
        '''
        L = db.select('select * from `%s` %s' % (cls.__table__, where), *args)
        return [ cls(**d) for d in L ]
    
    @classmethod
    def count_all(cls):
        '''
        'count(pk)', return int
        '''
        return db.select_int('select count(`%s`) from `%s`' % (cls.__primary_key__.name, cls.__table__))
    
    @classmethod
    def count_by(cls, where, *args):
        '''
        'count(pk)' with 'where', return int
        '''
        return db.select_int('select count(`%s`) from `%s` %s' % (cls.__primary_key__.name, cls.__table__, where), *args)
    
    def insert(self):
        self.pre_insert and self.pre_insert()
        params = {}
        for k, v in self.__mappings__.iteritems():
            if v.insertable:
                if not hasattr(self, k):
                    setattr(self, k, v.default)
                params[v.name] = getattr(self, k)
        db.insert('%s' % self.__table__, **params)
        return self
    
    def update(self):
        self.pre_update and self.pre_update()
        L = []
        args = []
        for k, v in self.__mappings__.iteritems():
            if v.updatable:
                if hasattr(self, k):
                    arg = getattr(self, k)
                else:
                    arg = v.default
                    setattr(self, k, arg)
                L.append('`%s`=?' % k)
                args.append(arg)
        pk = self.__primary_key__.name
        args.append(getattr(self, pk))
        db.update('update `%s` set %s where %s=?' % (self.__table__, ','.join(L), pk), *args)
        return self
    
    def delete(self):
        self.pre_delete and self.pre_delete()
        pk = self.__primary_key__.name
        args = (getattr(self, pk),)
        db.update('delete from `%s` where `%s`=?' % (self.__table__, pk), *args)
        return self

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    db.create_engine('www-data', 'www-data', 'test')
    db.update('drop table if exists user')
    db.update('create table user (id int primary key, name text, email text, password text, last_modified real)')
    import doctest
    doctest.testmod()
