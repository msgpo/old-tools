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
