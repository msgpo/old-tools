import os
import logging

from pyhocon import ConfigFactory

from utils import train_speech_recognizer, train_intent_recognizer

logging.basicConfig(level=logging.DEBUG)

def main():
    config_path = os.path.join('web', 'rhasspy.conf')
    logging.info('Loading configuration from %s' % config_path)

    config = ConfigFactory.parse_file(config_path)
    train_speech_recognizer(config)
    train_intent_recognizer(config)

if __name__ == '__main__':
    main()
