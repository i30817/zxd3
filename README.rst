zxd3
====

This utility uses sorting heuristics to diff two zips whose contents are
*related* but not named the same.
This way, it serves a different purpose than utilities like xdelta3-dir-patch
which are only effective for 1-to-1 matches in filenames.
It has two modes: compression takes two zip files, source and target and
produces a zxd3 patch (*not* usable by the xdelta3 standalone utility) of their
uncompressed, heuristically sorted, contents concatenated as a uncompressed byte
stream.

Patch takes a source zip and a zxd3 file and extracts the contents of the
original target zip to a given directory.

Arguments
---------

zxd3 [-h] [-c source.zip target.zip patch.zxd3 | -p source.zip patch.zxd3 out-dir]


Memory Requirements
-------------------
This program will not create temporary files on patch creation and only will
create the real output files during patch application.

Required memory is at least 256mb, probably more. Each of the 2 zips has a
sliding window of 64mb that it fills to create xdelta3 diffs, and the xdelta3
module doesn't consume memory view, so the 'usuable' part of those views has to
be converted to bytes array during encoding and decoding

Install
-------

zxd3 requires python 3.5 or later, mostly because the xdelta3 pypi library
requires it.

`The source for this project is available here
<https://github.com/i30817/zxd3>`_.

The project can be installed on linux machines by installing pip3 and running
`pip3 install --user zxd3` or `pip3 install --user
https://github.com/i30817/zxd3/archive/master.zip` for the latest master.

Since the xdelta pypi package has no windows version, this program doesn't work
there currently.

----



