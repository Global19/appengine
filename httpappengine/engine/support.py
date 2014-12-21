#!/usr/bin/python
# -*- coding: utf-8 -*-

"""
Copyright (c) 2014 windpro

Author  :   windpro
E-mail  :   windprog@gmail.com
Date    :   14-12-1
Desc    :   支持各种框架，目前支持django
"""

#支持django的一些方法
#=======================================================================================================================


def get_django_application():
    if "django_application" not in globals():
        # 在模块级别保存wsgi application
        from django.core.wsgi import get_wsgi_application
        #django 处理wsgi的函数
        django_application = get_wsgi_application()
        globals()['django_application'] = django_application
    else:
        django_application = globals()['django_application']
    return django_application


def __monkey_patch_django(_engine):
    from django.core import urlresolvers
    from .server import appengine_scheduler

    def get_engine_callback(callback):
        #resolve会递归查找，没必要返回多次。
        if callback.__name__ == "__engine_callback":
            return callback

        def __engine_callback(*args, **kwargs):
            return appengine_scheduler(_engine, callback, args, kwargs)
        return __engine_callback

    # 覆盖RegexURLResolver，使得执行handler的时候使用engine的调度器
    class PatchRegexURLResolver(urlresolvers.RegexURLResolver):
        def resolve(self, path):
            resolver_match = super(PatchRegexURLResolver, self).resolve(path)
            callback = resolver_match.func

            # 重新设置callback函数
            resolver_match.func = get_engine_callback(callback)
            return resolver_match

    urlresolvers.RegexURLResolver = PatchRegexURLResolver

    #patch staitc file handler
    from django.contrib.staticfiles import views
    serve = views.serve

    views.serve = get_engine_callback(serve)


def __patch_django_Server(_server, _engine):
    from .config import settings
    from .. import helper
    from .util import str_startswith_str_list
    import os

    def match_failure(environ, start_response):
        PATH_INFO = environ.get("PATH_INFO")
        if settings.DJANGO_URLS and not str_startswith_str_list(PATH_INFO, settings.DJANGO_URLS):
            return helper.not_found(start_response)
        else:
            # 动态载入django设置
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", settings.DJANGO_SETTINGS_MODULE)
            # 使django的callback 和 static file handler支持appengine调度器
            __monkey_patch_django(_engine)
            django_application = get_django_application()

            ret = django_application(environ=environ, start_response=start_response)
            # 处理结果。
            if ret is None:
                return helper.server_error(start_response)
            return ret

    _server.match_failure = match_failure


def patch_django(_server, _engine):
    # 当访问到django的时候才载入django引擎，节省资源
    __patch_django_Server(_server, _engine)

#=======================================================================================================================
