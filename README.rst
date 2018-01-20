zxd3
====

zxd3 uses heuristics to try to diff two zips whose contents are *related* but
not named the same. Zip contents never hit the disc except when recreating the
target at the final step of -p.

zxd3 patches are *not* usable by the xdelta3 standalone utility.

Arguments
---------

zxd3 [-h] [-c source.zip target.zip | -c2 source.zip target.zip patch.zxd3 | -p source.zip patch.zxd3 out-dir]

optional arguments:
   `-h, --help`
                        show this help message and exit
   `-c source.zip target.zip`
                        create a patch that transforms source zip into target
                        zip and extracts them. Patch will be named as
                        source.zip.zxd3
   `-c2 source.zip target.zip patch.zxd3`
                        create a patch that transforms source zip into target
                        zip and extracts them
   `-p source.zip patch.zxd3 out-dir`
                        apply a patch to source zip and extract contents of
                        the patch to out-dir

Memory Requirements
-------------------

Required memory is at least 256mb, possibly more. Each of the 2 zips has a
sliding window of 64mb that it fills to create xdelta3 diffs, and the xdelta3
module doesn't consume memoryview, so the 'usuable' part of those views has to
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

Since the xdelta3 pypi package has no windows version, this program doesn't work
there currently.

Credits
---------

.. class:: tablacreditos

+-------------------------------------------------+----------------------------------------------------+
| xdelta-dir-patcher was a inspiration            | https://github.com/endlessm/xdelta3-dir-patcher    |
+-------------------------------------------------+----------------------------------------------------+
| xdelta3 python bindings, library I use          | https://pypi.python.org/pypi/xdelta3               |
+-------------------------------------------------+----------------------------------------------------+
| xdelta, which made the above projects possible  | http://xdelta.org/                                 |
+-------------------------------------------------+----------------------------------------------------+
| natsort, library I use                          | https://pypi.python.org/pypi/natsort               |
+-------------------------------------------------+----------------------------------------------------+

