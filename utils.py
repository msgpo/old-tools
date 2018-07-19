import os
import sys
import re
import logging
import subprocess
import tempfile
from collections import defaultdict

# -----------------------------------------------------------------------------

def train_intent_recognizer(config):
    import rasa_nlu
    from rasa_nlu.train import do_train
    training_cfg = config['training']

    # Write training examples out to single file
    train_path = training_cfg['user_examples']
    with open(train_path, 'w+') as train_file:
        for example_path in training_cfg['example_files']:
            if not os.path.exists(example_path):
                continue

            # Copy contents
            with open(example_path, 'r') as example_file:
                for line in example_file:
                    print(line, file=train_file)

            # Back to beginining
            train_file.seek(0)
            logging.info('Training intent recognizer')
            do_train(cfg=rasa_nlu.config.load(training_cfg['intent_config']),
                     data=train_path,
                     path=training_cfg['intent_project_path'],
                     project=training_cfg['intent_project'],
                     num_threads=4)

    return train_path

# -----------------------------------------------------------------------------

def train_speech_recognizer(config):
    training_cfg = config['training']

    # Load examples
    intent_examples = load_training_phrases(training_cfg['example_files'])

    num_intents = len(intent_examples)
    num_examples = sum([len(v) for k, v in intent_examples.items()])
    logging.debug('Found %s example(s) from %s intent(s)' % (num_examples, num_intents))
    logging.debug(', '.join(sorted(intent_examples.keys())))

    # Write clean sentences to a file
    with open(training_cfg['user_sentences'], 'w+') as sentences_file:
        sentences = [example['clean']
                     for k, v in intent_examples.items()
                     for example in v]

        logging.debug('Writing %s sentence(s) to %s' % (len(sentences), sentences_file.name))
        for sentence in sentences:
            print(sentence, file=sentences_file)

        # Generate language model and vocabulary
        sentences_file.seek(0)
        lm_command = ['ngram-count',
                      '-interpolate',
                      '-text', sentences_file.name,
                      '-lm', training_cfg['user_language_model'],
                      '-write-vocab', training_cfg['user_vocab']]

        logging.debug('Generating custom language model')
        logging.debug(lm_command)
        subprocess.check_call(lm_command)

        logging.info('Generated custom language model')

    # Read dictionaries
    word_dict = defaultdict(set)
    for dict_path in training_cfg['dictionary_files']:
        if not os.path.exists(dict_path):
            continue

        logging.debug('Loading dictionary from %s' % dict_path)
        read_dict(dict_path, word_dict)

    # Check vocabulary
    vocab_words = []
    with open(training_cfg['user_vocab'], 'r') as vocab_file:
        for line in vocab_file:
            line = line.strip()
            if (len(line) == 0) or line.startswith('-') or line.startswith('<'):
                continue  # skip blank lines and silence phones

            vocab_words.append(line)

    logging.debug('Checking %s vocabulary word(s)' % len(vocab_words))
    unknown_words = set()
    for word in vocab_words:
        if not word in word_dict:
            unknown_words.add(word)

    if len(unknown_words) > 0:
        logging.debug('Generating pronounciations for unknown words')
        ws_pattern = re.compile(r'\s+')

        # Write words
        with tempfile.NamedTemporaryFile(mode='w', suffix='.g2p') as word_file:
            for word in unknown_words:
                # MUST use upper-case for phonetisaurus
                print(word.upper(), file=word_file)

            with tempfile.NamedTemporaryFile(mode='r+', suffix='.txt') as pronounce_file:
                word_file.seek(0)
                g2p_command = ['phonetisaurus-g2p',
                               '--model=' + training_cfg['g2p_fst'],
                               '--input=' + word_file.name,
                               '--isfile',
                               '--nbest=1',
                               '--words']

                logging.debug(g2p_command)
                subprocess.check_call(g2p_command, stdout=pronounce_file)

                # Add to unknown dictionary
                with open(training_cfg['unknown_dictionary'], 'w') as dict_file:
                    # Transform to dict format
                    # Phonetisaurus: WORD SCORE <s> PHONEMES </s>
                    # Dict: WORD PHONEMES
                    pronounce_file.seek(0)
                    for line in pronounce_file:
                        parts = ws_pattern.split(line)
                        word = parts[0].lower()
                        phonemes = parts[3:-2]
                        print(' '.join([word] + phonemes), file=dict_file)

                        # Add to mixed dictionary
                        word_dict[word].add(' '.join(phonemes))

        # Inform user and stop training
        logging.warn('There are %s unknown words: %s.' % (len(unknown_words), ', '.join(unknown_words)))
        logging.warn('See %s for possible pronounciations.' % training_cfg['unknown_dictionary'])

    # Write merged dictionary
    logging.debug('Writing mixed dictionary with %s word(s)' % len(word_dict))
    with open(training_cfg['mixed_dictionary'], 'w') as mixed_dict:
        for word, pronounces in sorted(word_dict.items()):
            for i, pronounce in enumerate(pronounces):
                if i > 0:
                    w = '{0}({1})'.format(word, i + 1)
                else:
                    w = word
                print(w.lower(), pronounce.upper(), file=mixed_dict)

    # Mix with base language model
    logging.info('Mixing with base language model')
    mix_command = ['ngram',
                   '-lm', training_cfg['base_language_model'],
                   '-lambda', str(training_cfg['mix_lambda']),
                   '-mix-lm', training_cfg['user_language_model'],
                   '-write-lm', training_cfg['mixed_language_model']]

    logging.debug(mix_command)
    subprocess.check_call(mix_command)

    return training_cfg['mixed_language_model']

# -----------------------------------------------------------------------------

def load_training_phrases(data_paths):
    intent_phrases = defaultdict(list)

    for data_path in data_paths:
        if not os.path.exists(data_path):
            continue

        with open(data_path, 'r') as data_file:
            intent_name = None
            intent_regex = re.compile(r'^##\s+intent:(.+)$')
            for line in data_file:
                line = line.strip()
                if line.startswith('##'):
                    match = intent_regex.search(line)
                    if match is not None:
                        # intent:<name>
                        intent_name = match.group(1)
                    else:
                        # Not an intent
                        intent_name = None
                elif intent_name is not None and line.startswith('-'):
                    # Example
                    raw_phrase = line[1:].strip()
                    phrase_text, entities = extract_entities(raw_phrase)
                    clean_text = sanitize_phrase(phrase_text)
                    intent_phrases[intent_name].append({
                        'raw': raw_phrase,
                        'text': phrase_text,
                        'clean': clean_text,
                        'entities': entities
                    })

    return intent_phrases

def sanitize_phrase(phrase):
    """
    Prepares a phrase to be used by the speech recognition system.

    Arguments:
    phrase -- text string

    Returns:
    text string with unusable characters/words removed

    Does the following:
    0) Lower-cases
    1) Removes apostrophes, commas, colons
    2) Replaces ampersands with 'and'
    3) Replaces digits with number words (2 -> two)
    4) Replaces ii and iii Roman numerals with two and three
    5) Dashes (-) are replaced with spaces
    6) Anything that's not whitespace, an underscore, or alphanumeric is replaced with whitespace.
    """
    phrase = phrase.lower()
    phrase = phrase.replace("'s", 's')  # remove apostrophes
    phrase = phrase.replace(',', '')  # remove commas
    phrase = phrase.replace(':', '')  # remove colons
    phrase = phrase.replace('&', 'and')  # replace &

    # Replace numbers with words
    phrase = re.sub(r'\b([0-9]+)\b', lambda m: num2words(int(m.group(1))), phrase)

    # Replace Roman numerals with words
    phrase = re.sub(r'\biii\b', 'three', phrase)
    phrase = re.sub(r'\bii\b', 'two', phrase)

    # Replace dashes with spaces
    phrase = phrase.replace('-', ' ')

    # Replace everything that's not:
    # 1) alpha-numeric
    # 2) an underscore
    # 3) whitespace
    return re.sub(r'[^a-z0-9_\s]', ' ', phrase)

# -----------------------------------------------------------------------------

def extract_entities(phrase):
    """
    Extracts embedded entity markings from a phrase.
    Returns the phrase with entities removed and a list of entities.

    The format [some text](entity name) is used to mark entities in a training phrase.
    """
    start = 0  # start of current value
    offset = 0  # number of chars removed from original phrase
    in_value = False  # True when inside [...]
    between_value_entity = False  # True at [...]^(...)
    in_entity = False  # True when inside (...)
    value = ''  # current value inside [...]
    entity = ''  # current entity inside (...)

    new_phrase = ""  # phrase with DSL stripped
    entities = []  # list of parsed entities

    for i, c in enumerate(phrase):
        if in_value and (c == ']'):
            # Value end
            offset += 1
            in_value = False
            between_value_entity = True
        elif in_value:
            # Inside value
            value += c
            new_phrase += c
        elif in_entity and (c == ')'):
            # Entity end
            offset += 1
            in_entity = False
            entities.append({
                'start': start,
                'end': (start + len(value)),
                'value': value,
                'entity': entity
            })
        elif in_entity:
            # Inside entity
            offset += 1
            entity += c
        elif between_value_entity and (c == '('):
            # Between value/entity
            offset += 1
            between_value_entity = False
            in_entity = True
        elif between_value_entity and (c != '('):
            # Not a [...](...) pattern, skip
            between_value_entity = False
            new_phrase += c
        elif c == '[':
            # Value start
            start = i - offset
            offset += 1
            in_value = True
            value = ''
            entity = ''
        else:
            # Regular character
            new_phrase += c
            start += 1

    return new_phrase, entities

# -----------------------------------------------------------------------------

def read_dict(dict_path, word_dict):
    with open(dict_path, 'r') as dict_file:
        for line in dict_file:
            line = line.strip()
            if len(line) == 0:
                continue

            word, pronounce = re.split('\s+', line, maxsplit=1)
            idx = word.find('(')
            if idx > 0:
                word = word[:idx]

            word_dict[word].add(pronounce.strip())

# -----------------------------------------------------------------------------

def play_wav(filename=None, data=None):
    args = ['aplay', '-q']

    if data is not None:
        # Use WAV data
        subprocess.run(args, input=data)
    else:
        # Use provided file name
        args.append(filename)
        subprocess.call(args)

# -----------------------------------------------------------------------------

def get_decoder(hmm_dir, dict_file, lm_file=None,
                keyphrase=None, kws_threshold=1e-40):

    import pocketsphinx

    # Configure the PocketSphinx decoder
    decoder_config = pocketsphinx.Decoder.default_config()
    decoder_config.set_string('-hmm', hmm_dir)

    if lm_file is not None:
        decoder_config.set_string('-lm', lm_file)
    else:
        decoder_config.set_string('-keyphrase', keyphrase)
        decoder_config.set_float('-kws_threshold', float(kws_threshold))

    decoder_config.set_string('-dict', dict_file)
    # decoder_config.set_string('-logfn', os.devnull)

    return pocketsphinx.Decoder(decoder_config)

def get_project(project_name, project_dir):
    from rasa_nlu.project import Project
    return Project(project=project_name,
                   project_dir=project_dir)
