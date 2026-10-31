import logging

LOG = 'urait.log'
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [%(filename)s:%(lineno)d] %(message)s',
    handlers=[
        logging.FileHandler(LOG, encoding='utf-8', mode='w'),
    ]
)
logger = logging.getLogger(__name__)