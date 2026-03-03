import logging
from flask import Flask
from logging.handlers import TimedRotatingFileHandler
from concurrent_log_handler import ConcurrentTimedRotatingFileHandler
import os
def init_app(app: Flask):
    """日志记录器初始化"""
    # 1.根据不同的化境设置logging根处理器的日志级别
    logging.getLogger().setLevel(logging.DEBUG if app.debug or os.getenv("FLASK_ENV") == "development" else logging.WARNING)

    # 2.设置日志存储的文件夹 如果不存在则创建
    log_folder = os.path.join(os.getcwd(), "storage", "log")
    if not os.path.exists(log_folder):
        os.makedirs(log_folder)

    # 3.定义日志的文件名
    log_file = os.path.join(log_folder, "app.log")

    # 4.设置日志的格式 并且让日志每天更新一次
    handler = ConcurrentTimedRotatingFileHandler(
        log_file,
        when='midnight',
        interval=1,
        backupCount=30,
        encoding='utf-8')

    formatter = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(filename)s -> %(funcName)s line:%(lineno)d [%(levelname)s]: %(message)s"
    )
    # 5.设置要处理的等级和处理格式 获取实例并添加处理器
    handler.setLevel(logging.DEBUG if app.debug or os.getenv("FLASK_ENV") == "development" else logging.WARNING)
    handler.setFormatter(formatter)
    logging.getLogger().addHandler(handler)

    # 6.在开发环境下同时将日志输出到控制台
    if app.debug or os.getenv('FLASK_ENV') == 'development':
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logging.getLogger().addHandler(console_handler)