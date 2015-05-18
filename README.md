# webapp-python

使用Python实现的该Webapp。

1. www/transwarp/db.py
    根据DB-API实现的MySQL操作工具，管理connection / transcation。

2. www/transwarp/orm.py
    使用Python内建的Metaclass实现的关系对象模型映射工具。

3. www/transwarp/web.py
    简单的WSGI框架，对Request / Response/ Server进行封装，提供RESTful风格的API。

4. www/urls.py
    业务处理模块。

5. 使用Python的第三方模块Jinja2和Markdown2生网页模板，使用UIkit制定网页样式，使用Vue.js实现网页的MVVM模式。

6. www/pymonitor.py
    使用Python的第三方模块Watchdog监听文件系统，实现开发阶段的热部署。

7. fabfile.py
    使用Python的第三方模块Fabric实现自动化部署

8. conf/supervisor/awesome.conf
    使用Python的第三方模块Supervisor管理WSGI Server进程，WSGI Server使用纯Python实现的Gunicorn。

9. conf/nginx/awesome
    使用Nginx实现请求反向代理，分发动/静态资源请求。
