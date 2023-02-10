import logging

class BotHandler(logging.StreamHandler):
    def __init__(self):
        logging.StreamHandler.__init__(self)
        fmt = '%(asctime)-18s %(levelname)-8s: %(message)s'
        fmt_date = '%Y-%m-%d %T'
        formatter = logging.Formatter(fmt, fmt_date)
        self.setFormatter(formatter)