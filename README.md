Tools for rhasspy Voice Assistant Toolkit
==================================================

These tools are needed by the [rhasspy voice
assistant](https://github.com/synesthesiam/rhasspy-assistant). I have collected
and compiled them here to expidite the installation of rhasspy. It is
recommended that you build and install the tools from source yourself, but these
pre-built binaries are a good place for beginners to start.

The available tools are:

* `phonetisaurus` - guesses word pronunciations
    * Source available at
      [https://github.com/AdolfVonKleist/Phonetisaurus](https://github.com/AdolfVonKleist/Phonetisaurus)
    * My finite state transducer (FST) was training using the [Installing
      Phonetisaurus, m2m-aligner and
      MITLM](https://jasperproject.github.io/documentation/installation/) from
      Jasper's documentation
* `srilm` - generates language model from training phrases
    * Source and license available at
      [http://www.speech.sri.com/projects/srilm/](http://www.speech.sri.com/projects/srilm/)
    * Requires [modifications](https://github.com/G10DRAS/SRILM-on-RaspberryPi)
      to build on ARM systems (like the Raspberry Pi)
* `pocketsphinx` - speech to text
    * Source available at [https://github.com/cmusphinx/pocketsphinx](https://github.com/cmusphinx/pocketsphinx)
    * Acoustic and language models can be [downloaded separately](https://sourceforge.net/projects/cmusphinx/files/Acoustic%20and%20Language%20Models/)
* `pico-tts` - text to speech
    * Should be available from your distribution's package repository (`sudo apt-get install libttspico-utils`)
    * If it's missing, install with `sudo dpkg -i *.deb`

Web Server
------------

A small web server is included here to play around with the tools. This is not
required to get rhasspy running inside Home Assistant, but can be useful for
exploring how rhasppy works and understanding how it can be extended/customized.

Before creating a virtual environment for the web server, make sure you have the necessary system packages installed:

* General
    * `build-essential`
    * `git`
* Python
    * `python3`
    * `python3-dev`
    * `python3-pip`
    * `python3-venv`
* pocketsphinx
    * `libasound2-dev`
    * `libpulse-dev`
    * `swig`
* rasaNLU
    * `libatlas-dev`
    * `libatlas-base-dev`
* rhasspy
    * `libpicotts-utils`

You can install them all at once with a single command:

    sudo apt-get install build-essential \
        python3 python3-dev python3-pip python3-venv \
        libasound2-dev libpulse-dev swig \
        libatlas-dev libatlas-base-dev \
        libpicotts-utils

Now, follow the instructions below to install the necessary Python libraries
inside a virtual environment.

1. Install [pipenv](https://docs.pipenv.org/):

    sudo -H python3 -m pip install pipenv
    
2. Install Python dependencies:

    cd rhasppy-tools
    
    pipenv install
    
3. Install `snowboy`:

    pipenv install https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz
    
4. Install `spaCy` language model

    pipenv run python -m spacy download en
    
5. Start web server:

    ./web-server
    
6. Open a web browser and go to [http://localhost:8080](http://localhost:8080)

Edit `web/rhasspy.conf` to change the settings for the web server.

Training
----------

A small `train` script is provided to allow for command-line training. Edit
`web/rhasspy.conf` to change the settings for training.
