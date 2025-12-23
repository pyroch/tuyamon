import logging
# Base logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)

# To import
log = logging.getLogger(__name__)
log.setLevel(logging.INFO)