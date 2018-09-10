Building Phonetisaurus
===========================

Rhasspy uses an old version of phonetisaurus that was originally built using the
documentation from
[Jasper](https://jasperproject.github.io/documentation/installation/). To make
things a bit easier, I've uploaded the code to Github and included build
instructions here. There are just two steps:

1. Build `openfst-1.3.4`
2. Build `phonetisaurus-g2p`

Building OpenFST
--------------------

The version of phonetisaurus Rhasspy uses requires a correspondingly old version
of OpenFST. It takes *forever* to build. **Forever**.

First, make sure you have the right tools installed:

    sudo apt-get update
    sudo apt-get install git build-essential
    
Grab my copy of the source code and get it started building:

    git clone https://github.com/synesthesiam/openfst-1.3.4.git
    cd openfst-1.3.4
    ./configure --enable-compact-fsts --enable-const-fsts --enable-far --enable-lookahead-fsts --enable-pdt
    make
    
Consider raising a family and having a fulfilling career while you wait. When it
finishes, copy the compiled libraries over to wherever `rhasspy-tools` is
installed:

    cp src/lib/.libs/libfst.so* ~/rhasspy-tools/phonetisaurus/lib/$ARCH/

where `$ARCH` is probably `x86_64` if you're on a desktop/laptop/server or
`arm7l` on a Raspberry Pi. Run `uname -m` if you have no clue.

Building Phonetisaurus
----------------------------

After building OpenFST, this step is a breeze. First, grab the code:

    https://github.com/synesthesiam/phonetisaurus-2013.git
    cd phonetisaurus-2013/src
    mkdir -p bin
    
Now we need to make the `phonetisaurus-g2p` tool, but it has to be aware of
where the OpenFST artifacts are. Rather than have you install an old version of
OpenFST on your system, you can just point right at them:

    CPPFLAGS=-I/path/to/openfst-1.3.4/src/include LDFLAGS=-L/path/to/openfst-1.3.4/src/lib/.libs/ make bin/phonetisaurus-g2p
    
where `/path/to/openfst-1.3.4` is the full path to wherever you downloaded and built OpenFST.

When that finishes (5-10 minutes), copy the tool over to `rhasspy-tools`:

    cp bin/phonetisaurus-g2p ~/rhasspy-tools/phonetisaurus/bin/$ARCH/
    
where `$ARCH` is the same as above. You can verify things worked by running
`phonetisaurus-g2p`:

    cd ~/rhasspy-tools/phonetisaurus/
    ./phonetisaurus-$ARCH --model=etc/g014b2b.fst --input=SKRILLEX
    
Again, replace `$ARCH` with your architecture. If everything went well, you'll
get a guess at how to pronounce "Skrillex":

    27.9855 <s> S K R IH L AH K S </s>
    
Check out the Phoneme Set section of [The CMU Pronouncing
Dictionary](http://www.speech.cs.cmu.edu/cgi-bin/cmudict) page for more
information.
