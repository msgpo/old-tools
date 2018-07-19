import os
import sys
import logging
import json
import io
import wave
import tempfile
import subprocess
import re
import time
import threading
from uuid import uuid4
from collections import defaultdict

import requests
from pyhocon import ConfigFactory

import pyttsx3
import pocketsphinx
import rasa_nlu

from flask import Flask, request, render_template, send_from_directory, make_response

from utils import (train_speech_recognizer, train_intent_recognizer,
                   load_training_phrases, read_dict, play_wav,
                   get_decoder, get_project)

logging.basicConfig(level=logging.DEBUG)

# ---------------------------------------------------------------------

config_path = os.path.join('web', 'rhasspy.conf')
logging.info('Loading configuration from %s' % config_path)

config = ConfigFactory.parse_file(config_path)

# ---------------------------------------------------------------------

# Load microphone/speaker info from pyAudio
audio_devices = []

try:
    import pyaudio
    audio = pyaudio.PyAudio()
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        audio_devices.append(info)

    audio.terminate()
except:
    logging.exception('Failed to get audio devices')

# ---------------------------------------------------------------------

# Gather voices
voices = defaultdict(list)
pyttsx_engine = pyttsx3.init()
voices['pyttsx3'] = { v.id: v.name for v in pyttsx_engine.getProperty('voices') }

# Known Mary TTS voices
voices['mary-tts'] = {
    'cmu-slt-hsmm': 'SLT (CMU Female)',
    'cmu-bdl-hsmm': 'BDL (CMU Male)',
    'cmu-rms-hsmm': 'RMS (CMU Male)',
    'dfki-spike-hsmm': 'Spike (British Male)',
    'dfki-prudence-hsmm': 'Prudence (British Female)',
    'dfki-poppy-hsmm': 'Poppy (British Female)',
    'dfki-obadiah-hsmm': 'Obadiah (British Male)'
}

# Load phoneme map from Sphinx to eSpeak
phoneme_map = os.path.join('web', 'phoneme.map')
phonemes = {}
with open(phoneme_map, 'r') as phoneme_file:
    for line in phoneme_file:
        line = line.strip()
        if (len(line) == 0) or line.startswith('#'):
            continue  # skip blanks and comments

        parts = line.split(' ', maxsplit=1)
        phonemes[parts[0]] = parts[1]

# Load dictionaries
dictionary_files = config['training']['dictionary_files']
word_dict = defaultdict(set)
for dict_path in dictionary_files:
    if not os.path.exists(dict_path):
        continue

    logging.debug('Loading dictionary from %s' % dict_path)
    read_dict(dict_path, word_dict)

# ---------------------------------------------------------------------

# Create web server
app = Flask('rhasspy', template_folder=os.path.join('web', 'templates'))
app.secret_key = str(uuid4())

# Automatically reload template files if they're changed on disk.
# Used for debugging/development.
app.config['TEMPLATES_AUTO_RELOAD'] = True

# ---------------------------------------------------------------------
# Static Routes
# ---------------------------------------------------------------------

@app.route('/css/<path:filename>', methods=['GET'])
def css(filename):
    return send_from_directory(os.path.join('web', 'static', 'css'), filename)

@app.route('/js/<path:filename>', methods=['GET'])
def js(filename):
    return send_from_directory(os.path.join('web', 'static', 'js'), filename)

@app.route('/img/<path:filename>', methods=['GET'])
def img(filename):
    return send_from_directory(os.path.join('web', 'static', 'img'), filename)

@app.route('/webfonts/<path:filename>', methods=['GET'])
def webfonts(filename):
    return send_from_directory(os.path.join('web', 'static', 'webfonts'), filename)

# ---------------------------------------------------------------------

@app.route('/')
def index():
    return render_template('index.html', current_page='')

@app.route('/about')
def about():
    return render_template('about.html', current_page='about')

# ---------------------------------------------------------------------

wake_statuses = defaultdict(bool)
wake_decoder = None

@app.route('/wake-word', methods=['GET', 'POST'])
def wake():
    global wake_decoder

    if request.method == 'POST':
        system = request.form['system']
        if system == 'pocketsphinx':
            # Pocketsphinx
            wake_statuses[system] = 'recording'
            if wake_decoder is None:
                ps_config = config['pocketsphinx']
                training_cfg = config['training']

                # Listen with the default acoustic model and mixed dictionary
                hmm = ps_config['acoustic_model']
                dic = ps_config['dictionary']
                keyphrase = request.form['keyphrase']
                kws_threshold = float(ps_config['kws_threshold'])

                def detect():
                    from pocketsphinx import Pocketsphinx, Ad
                    ad = Ad(None, 16000)  # default input
                    decoder = Pocketsphinx(lm=False,
                                           hmm=hmm,
                                           dic=dic,
                                           keyphrase=keyphrase,
                                           kws_threshold=kws_threshold)

                    buf = bytearray(2048)
                    with ad:
                        with decoder.start_utterance():
                            while ad.readinto(buf) >= 0:
                                decoder.process_raw(buf, False, False)
                                if decoder.hyp():
                                    with decoder.end_utterance():
                                        logging.info('Wake word detected for %s' % system)
                                        wake_statuses[system] = 'detected'
                                        break

                # Run detection in sepearate thread
                thread = threading.Thread(target=detect, daemon=True)
                thread.start()
                logging.debug('Listening for %s with %s' % (keyphrase, system))

            return system
        elif system == 'snowboy':
            # Snowboy
            snowboy_cfg = config['snowboy']
            model_path = request.form['model']
            sensitivity = float(snowboy_cfg['sensitivity'])
            audio_gain = float(snowboy_cfg['audio_gain'])

            from snowboy import snowboydecoder
            detector = snowboydecoder.HotwordDetector(
                model_path, sensitivity=sensitivity, audio_gain=audio_gain)

            def stop():
                wake_statuses[system] = 'detected'
                detector.terminate()

            def detect():
                detector.start(stop)

            # Run detection in sepearate thread
            thread = threading.Thread(target=detect, daemon=True)
            thread.start()
            logging.debug('Listening for %s with %s' % (os.path.basename(model_path), system))

            return system
        elif system == 'precise':
            # Mycroft Precise
            precise_cfg = config['mycroft_precise']
            model_path = request.form['model']

            from precise_runner import PreciseEngine, PreciseRunner
            engine = PreciseEngine('precise-engine', model_path)


            def detect():
                event = threading.Event()
                runner = PreciseRunner(engine, on_activation=lambda: event.set())
                runner.start()
                event.wait()
                wake_statuses[system] = 'detected'
                runner.stop()

            thread = threading.Thread(target=detect, daemon=True)
            thread.start()
            logging.debug('Listening for %s with %s' % (os.path.basename(model_path), system))

            return system
        else:
            return make_response('Unknown system: %s' % system, 500)

    return render_template('wake-word.html',
                           current_page='wake-word',
                           config=config,
                           basename=os.path.basename)

@app.route('/wake-status')
def wake_status():
    json_statuses = json.dumps(wake_statuses)

    for system, status in list(wake_statuses.items()):
        if status == 'detected':
            del wake_statuses[system]

    return json_statuses

# ---------------------------------------------------------------------

project = None
@app.route('/intent-recognition', methods=['GET', 'POST'])
def intent():
    global project
    rasa_cfg = config['rasa_nlu']

    if request.method == 'POST':
        command = request.data.decode('utf-8')
        logging.debug('Sending command: %s' % command)

        if project is None:
            project = get_project(rasa_cfg['project_name'],
                                  rasa_cfg['project_dir'])

        intents = project.parse(command)
        return json.dumps(intents)

    # Re-load training phrases
    example_files = config['training']['example_files']
    intent_examples = load_training_phrases(example_files)

    return render_template('intent-recognition.html',
                           current_page='intent-recognition',
                           intent_examples=intent_examples,
                           example_files=example_files,
                           rasa_cfg=rasa_cfg)

@app.route('/train-intent', methods=['POST'])
def train_intent():
    global project
    result = train_intent_recognizer(config)
    project = None
    return result

# ---------------------------------------------------------------------

@app.route('/text-to-speech', methods=['GET', 'POST'])
def tts():
    if request.method == 'POST':
        text = request.form['text']
        if len(text) == 0:
            return make_response('No text given', 500)

        engine = request.form.get('engine', '').lower()
        voice = request.form.get('voice', 'Default Voice')

        logging.debug('Speaking with engine %s, voice%s: %s' % (engine, voice, text))

        if engine == 'pico-tts':
            # Pico
            with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as wav_file:
                subprocess.check_call(['pico2wave',
                                        '-w', wav_file.name,
                                        text])

                wav_file.seek(0)
                play_wav(filename=wav_file.name)
        elif engine == 'mary-tts':
            # MaryTTS
            if not (text.endswith('.') or text.endswith('!') or text.endswith('?')):
                # Need some kind of punctuation for Mary to sound right
                text = text + '.'

            params = {
                'INPUT_TEXT': text,
                'INPUT_TYPE': 'TEXT',
                'AUDIO': 'WAVE',
                'OUTPUT_TYPE': 'AUDIO',
                'LOCALE': 'en-US',
                'VOICE': 'cmu-slt-hsmm'
            }

            if (voice != 'Default Voice'):
                params['VOICE'] = voice

            result = requests.get(config['marytts']['url'], params=params)
            if result.ok:
                play_wav(data=result.content)
            else:
                result.raise_for_status()
        else:
            # PyTTSX
            if (voice != 'Default Voice'):
                pyttsx_engine.setProperty('voice', voice)

            pyttsx_engine.say(text)
            pyttsx_engine.runAndWait()

        return text

    return render_template('text-to-speech.html',
                            current_page='text-to-speech',
                            voices=voices,
                            devices=audio_devices)

@app.route('/pronounce', methods=['POST'])
def pronounce():
    # Transform Sphinx phonemes into eSpeak phonemes
    phoneme_str = request.data.decode('utf-8').strip().upper()
    logging.debug('Pronouncing: %s' % phoneme_str)
    espeak_str = "[['%s]]" % ''.join(phonemes.get(p, p)
                                        for p in phoneme_str.split())

    subprocess.check_call(['espeak', espeak_str,
                            '-s', '80'])
    return espeak_str

@app.route('/dictionary', methods=['POST'])
def dictionary():
    word = request.data.decode('utf-8').strip().lower()
    logging.debug('Getting pronounciations for %s' % word)
    in_dictionary = True
    pronounces = list(word_dict[word])
    if len(pronounces) == 0:
        in_dictionary = False

        # Use phonetisaurus to guess pronounciations
        g2p_command = ['phonetisaurus-g2p',
                        '--model=' + config['training']['g2p_fst'],
                        '--input=' + word.upper(),  # upper-case required
                        '--nbest=5',
                        '--words']

        logging.debug(g2p_command)
        proc = subprocess.Popen(g2p_command, stdout=subprocess.PIPE)
        ws_pattern = re.compile(r'\s+')

        for line in proc.stdout:
            line = line.decode('utf-8')
            parts = ws_pattern.split(line)
            phonemes = ' '.join(parts[3:-2])
            pronounces.append(phonemes)

    return json.dumps({
        'dictionary': in_dictionary,
        'pronounciations': pronounces
    })

decoders = {}
@app.route('/speech-to-text', methods=['GET', 'POST'])
def stt():
    global decoders
    if request.method == 'POST':
        source = request.args.get('source', 'microphone')
        selected_lm = request.args.get('lm', 'user')

        decoder = decoders.get(selected_lm, None)
        if decoder is None:
            ps_config = config['pocketsphinx']
            training_cfg = config['training']
            language_model = training_cfg['user_language_model']

            if selected_lm == 'base':
                language_model = training_cfg['base_language_model']
            elif selected_lm == 'mixed':
                language_model = training_cfg['mixed_language_model']

            decoder = get_decoder(ps_config['acoustic_model'],
                                  training_cfg['mixed_dictionary'],
                                  lm_file=language_model)

            # Cache for later
            decoders[selected_lm] = decoder

        if (source == 'microphone') and ('wav_dir' in config):
            # Create directory to store WAV files
            wav_dir = config['wav_dir']
            os.makedirs(wav_dir, exist_ok=True)
        else:
            wav_dir = None  # don't store WAVs

        # Open up WAV data to get at rate, width, channel info
        with io.BytesIO(request.data) as wav_data:
            if wav_dir is not None:
                # Save copy of the *original* WAV (unknown sample rate, etc.)
                wav_path = os.path.join(wav_dir, '%s.wav' % int(time.time()))
                with open(wav_path, 'wb') as wav_copy:
                    wav_copy.write(wav_data.read())

            wav_data.seek(0)

            # Check if WAV is in the correct format.
            # Convert with sox if not.
            with wave.open(wav_data, mode='rb') as wav_file:
                rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                logging.debug('rate=%s, width=%s, channels=%s.' % (rate, width, channels))

                if (rate != 16000) or (width != 2) or (channels != 1):
                    # Convert to 16-bit 16Khz mono (required by pocketsphinx acoustic models)
                    logging.debug('Need to convert to 16-bit 16Khz mono.')
                    with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as out_wav_file:
                        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb') as in_wav_file:
                            in_wav_file.write(request.data)
                            in_wav_file.seek(0)
                            subprocess.check_call(['sox',
                                                in_wav_file.name,
                                                '-r', '16000',
                                                '-e', 'signed-integer',
                                                '-b', '16',
                                                '-c', '1',
                                                out_wav_file.name])

                            out_wav_file.seek(0)

                            # Use converted data
                            with wave.open(out_wav_file, 'rb') as wav_file:
                                data = wav_file.readframes(wav_file.getnframes())
                else:
                    # Use original data
                    data = wav_file.readframes(wav_file.getnframes())

        # Process data as an entire utterance
        decoder.start_utt()
        decoder.process_raw(data, False, True)
        decoder.end_utt()

        if decoder.hyp():
            return decoder.hyp().hypstr

        return ''

    return render_template('speech-to-text.html',
                            current_page='speech-to-text',
                            devices=audio_devices,
                            dictionary_files=dictionary_files,
                            config=config)

@app.route('/train-speech', methods=['POST'])
def train_speech():
    result = train_speech_recognizer(config)
    decoders.clear()
    return result

# ---------------------------------------------------------------------

@app.route('/train-speech-and-intent', methods=['POST'])
def train_speech_and_intent():
    global project
    train_speech_recognizer(config)
    train_intent_recognizer(config)
    project = None
    decoders.clear()
    return 'OK'

# ---------------------------------------------------------------------
