Building SRILM Toolkit
===========================

Rhasspy uses the Stanford Research Institute Language Modeling
([SRILM](http://www.speech.sri.com/projects/srilm/)) toolkit to train its speech
recognizer. I've included binaries for the `x86_64` and `armv7l` systems that I
have access to, but I can't build for every possible combination of
hardware/operating system out there.

Building the SRILM toolkit isn't terribly difficult, but it can take quite a
while on a Raspberry Pi (30 minutes to an hour). Luckily, you only need to do
this once wherever you plan to do Rhasspy's training.

Downloading the Source Code
----------------------------------

The first step is downloading the SRILM toolkit source code. You need to obtain
a "license" to do this, which really just means you [go to their download
page](http://www.speech.sri.com/projects/srilm/download.html), give them your
e-mail address, and agree to their terms (non-commercial use, etc.). Once you do
that, you'll have a `.tar.gz` file with the source code (mine is
`srilm-1.7.2.tar.gz`).

Building the Toolkit
-------------------------

First, we need to extract the source code:

    mkdir -p srilm-1.7.2
    mv srilm-1.7.2.tar.gz srilm-1.7.2/
    cd srilm-1.7.2
    tar -xvf srilm-1.7.2.tar.gz
    
Make sure to change `1.7.2` to whatever version you have downloaded. Next, make
sure you have the right system packages installed:

    sudo apt-get update
    sudo apt-get install build-essential tcl-dev

The next steps will depend on whether you're building on a Raspberry Pi or not.
If you're on anything, it's likely the instructions in `INSTALL` will work just
fine for you. I'd suggest following them, as anything I put here will eventually
be out of date.

### Building on a Raspberry Pi
    
We need to make some modifications for the Raspberry Pi. All credit for this
information goes to [this
person](https://github.com/G10DRAS/SRILM-on-RaspberryPi). I've simply rolled up
those changes and made them available in the `rhasspy-tools` repository.

I assume you're still in the `srilm-1.7.2` directory where the code is
extracted. Pull down the modified `machine-type` script and `Makefile`:

    wget -O common/Makefile.machine.armv7l https://raw.githubusercontent.com/synesthesiam/rhasspy-tools/master/srilm/common/Makefile.machine.armv7l
    wget -O sbin/machine-type https://raw.githubusercontent.com/synesthesiam/rhasspy-tools/master/srilm/sbin/machine-type
    
Now you should be able to build it:

    SRILM=`pwd` make World
    
I suggest going for a walk or watching a movie. It's going to be a while. After
it finishes, and assuming no errors, you will want to copy the following files
over to wherever you have `rhasspy-tools` installed:

    cp bin/armv7l/ngram bin/armv7l/ngram-count ~/rhasspy-tools/srilm/bin/armv7l/

Try running the Rhasspy training again and it should work!
