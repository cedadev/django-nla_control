import logging
import os
from nla_site.settings import *
import datetime

def setup_logging(module_name):
    # setup the logging
    try:
        log_path = NLA_LOG_PATH
    except:
        log_path = "./"

    # Make the logging dir if it doesn't exist
    if not os.path.isdir(log_path):
        os.makedirs(log_path)

    date = datetime.datetime.utcnow()
    date_string = "%d%02i%02iT%02i%02i%02i" % (date.year, date.month, date.day, date.hour, date.minute, date.second)
    log_fname = log_path + "/" + module_name+ "_" + date_string

    logging.basicConfig(filename=log_fname, level=logging.DEBUG)
