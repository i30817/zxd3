#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
#    zxd3
#    Copyright (C) 2018 i30817
#
#   This library is free software; you can redistribute it and/or
#   modify it under the terms of the GNU Lesser General Public
#   License as published by the Free Software Foundation; either
#   version 2.1 of the License, or (at your option) any later version.
#
#   This library is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#   Lesser General Public License for more details.
#
#   You should have received a copy of the GNU Lesser General Public
#   License along with this library; if not, write to the Free Software
#   Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301
#   USA

from __future__ import print_function
import argparse
import sys
import signal
import collections
import tarfile
import io
import os
import pickle
from zipfile import ZipFile
from io import BytesIO
from functools import reduce
from itertools import zip_longest, starmap

FILE_FORMAT_VERSION = b'1.0'
MAGIC = b'zxd3'
#don't need in-band file flags besides these two yet (or hopefully never)

try:
    #https://pypi.python.org/pypi/natsort
    from natsort import natsorted, natsort_keygen, ns
except Exception as e:
    print("Please install natsort. You can install the most recent version with 'pip3 install --user natsort'", file=sys.stderr)
    sys.exit(1)
try: #tried to use subprocess... failed because this needs to stream 2 input arguments...
    #https://pypi.python.org/pypi/xdelta3
    import xdelta3
except Exception as e:
    print("Please install xdelta3. You can install the most recent version with 'pip3 install --user xdelta3'", file=sys.stderr)
    sys.exit(1)

class OrderedDefaultdict(collections.OrderedDict):
    """ A defaultdict with OrderedDict as its base class. """

    def __init__(self, default_factory=None, *args, **kwargs):
        if not (default_factory is None
                or isinstance(default_factory, collections.Callable)):
            raise TypeError('first argument must be callable or None')
        super(OrderedDefaultdict, self).__init__(*args, **kwargs)
        self.default_factory = default_factory  # called by __missing__()

    def __missing__(self, key):
        if self.default_factory is None:
            raise KeyError(key,)
        self[key] = value = self.default_factory()
        return value

    def __reduce__(self):  # optional, for pickle support
        args = (self.default_factory,) if self.default_factory else tuple()
        return self.__class__, args, None, None, self.iteritems()

    def __repr__(self):  # optional
        return '%s(%r, %r)' % (self.__class__.__name__, self.default_factory,
                               list(self.iteritems()))

def tree(): return OrderedDefaultdict(tree)

def depth_first_in_order(list_out, tree):
    temp = []
    for key, t in tree.items():
        if not t:
            temp.append(key)

    def ignore_extension(path):
        (_, _, name) = path.rpartition('/')
        (lname, _, _) = name.rpartition('.')
        return lname
 
    natsort_key = natsort_keygen(key=ignore_extension, alg=ns.IGNORECASE)
    temp.sort(key=natsort_key)
    list_out.extend(temp)

    for key, t in tree.items():
        if t:
            depth_first_in_order(list_out, t)

#This algorithm first sorts the list of zip files by a path sort (to get a similar if not always equal order to directories).
#then it builds a file/dir tree it iterates depth-first pre-order, where it groups and sorts 'naturally' files of the same dirs 
#(doesn't consider extensions because of several corner cases in zips with similar but differently named or segmented files)

#Depth-first pre-order is important because:
#if two dumping formats, one places the audio tracks files inside a dir and the main track at the top dir,
#the other all in a single file, we want to compare the main (first in a dump) tracks first, not a data
#track to a audio track which is what in-order or post-order order could result in.
#names (and not extensions) in dirs natural order is important because:
#We do not want to lose any implicit name ordering or end with track1.bin followed by track11.BIN and formats like .gdi and .cue
#can segment large files in different extensions.
def zip_to_list_extensions(zfile):
    zip_tree = tree()
    #in order to maximize the chance of the two zip files having the same depth-first order (instead of one based on zip creation)
    for path in natsorted(zfile.namelist(), alg=ns.PATH):
        #directories will not be part of the tar
        if path.endswith("/"):
            continue
        (prev, _, _) = path.rpartition('/')
        #this is actually building the tree just by referencing
        t = zip_tree
        for d in prev.split('/'):
            t = t[d]
        t[path]

    #now iterate depth first in-order and sort
    final_files = []
    depth_first_in_order(final_files, zip_tree)

    def lb0(f):
        return zfile.getinfo(f).file_size

    return (list(map(lb0, final_files)), final_files)

def bytesgen(zip_file, list_f):
    '''
    This returns as much as it can from the byte stream of the zip in list_f order

    Default source buffer size in XDELTA3 is 64MB
    source: https://github.com/jmacd/xdelta/blob/wiki/TuningMemoryBudget.md
    We will have two of them at a time here (one for each stream)
    Unfortunately  we need to clone the memory view at some point.

    '''
    MAX = 67108864
    buf = bytearray(MAX)
    view = memoryview(buf)
    offset = 0

    for file_being_read in list_f:
        out_file_size = zip_file.getinfo(file_being_read).file_size

        #print(file_being_read + " from : "+ str(zip_file))

        with zip_file.open(file_being_read) as file_in_zip:
            while out_file_size:
                tmp_consumed = file_in_zip.readinto(view[offset:])
                out_file_size -= tmp_consumed
                offset += tmp_consumed
                if offset == MAX:
                    offset = 0
                    yield view

    yield view[0:offset]

def xdelta3gen( source_bytes, target_bytes ):
    #if source bytes finished, everything remaining is a target bytes
    if not source_bytes:
        sources_bytes = b''
    #if target bytes finished, we should stop
    if not target_bytes:
        return None
    #these are memoryviews and python xdelta3 lib doesn't like that...
    return xdelta3.encode(bytes(source_bytes), bytes(target_bytes))

def compress( source_f, target_f, patch ):
    #zip files are sort of like a directory tree
    #however we can't depend on the the directory structure being the same between the 2 zip to diff (though they usually are).
    #In order to create a effective delta between zips with different file names, we have to use heuristics to relate the files.
    with ZipFile(source_f, 'r') as source_z, ZipFile(target_f, 'r') as target_z:
        (source_sizes, ext1) = zip_to_list_extensions(source_z)
        (target_sizes, ext2) = zip_to_list_extensions(target_z)

        gen = zip_longest(bytesgen(source_z, ext1), bytesgen(target_z, ext2))
        x3gen = starmap(xdelta3gen, gen)

        if not patch.endswith(".zxd3"):
            patch += ".zxd3"

        with open(patch, 'wb') as out:
            #write magic for file in-band id and version for later versions
            pickle.dump( MAGIC, out, protocol=pickle.HIGHEST_PROTOCOL)
            pickle.dump( FILE_FORMAT_VERSION, out, protocol=pickle.HIGHEST_PROTOCOL)
            #write target (filename, size) list
            pickle.dump( zip(target_sizes, ext2), out, protocol=pickle.HIGHEST_PROTOCOL)
            for x in x3gen:
                if x:
                    #print("writing patch "+str(len(x)))
                    pickle.dump(x, out, protocol=pickle.HIGHEST_PROTOCOL)
                else:
                    break

def pickle_gen(patch):
        while True:
            x = pickle.load(patch)
            #print("reading patch "+str(len(x)))
            yield x

def xdelta3dec( source_bytes, patch_bytes ):
    #if source bytes finished, everything remaining is a patch bytes
    if not source_bytes:
        source_bytes = b''
    #if this happens either the patchfile is corrupt or there is a bug.
    #Every write and read must have a patch file written and read.
    assert patch_bytes
    #these are memoryviews and python xdelta3 lib doesn't like that...
    return xdelta3.decode(bytes(source_bytes), patch_bytes)

def patch( source_f, patch_f, out_dir):
    if os.path.isfile(out_dir):
        raise Exception('can\'t write patched files to a file')

    with ZipFile(source_f, 'r') as source_z:

        (source_sizes, ext) = zip_to_list_extensions(source_z)

        with open(patch_f, 'rb') as patch:
            STORED_MAGIC = pickle.load(patch)
            assert STORED_MAGIC == MAGIC
            #currently unused but could be used backwards compatibility in the future
            file_version = pickle.load(patch)

            files_to_write = list(pickle.load(patch))

            if not len(files_to_write):
                return

            gen = zip_longest(bytesgen(source_z, ext), pickle_gen(patch))
            x3dec = starmap(xdelta3dec, gen)

            index = 0
            x = next(x3dec)
            for (out_file_size, out_file) in files_to_write:
                #the out file came from a zip file so its seperator is always /, normpath fixes it on windows
                new_file = os.path.join( out_dir, os.path.normpath(out_file) )
                os.makedirs(os.path.dirname(new_file), exist_ok=True)
                with open(new_file, 'wb+') as current:
                    while out_file_size:
                        if index == len(x): #feed the bytes stream if it was all read
                            index = 0
                            x = next(x3dec)
                        tmp_len = min(out_file_size, len(x) - index)
                        tmp_consumed = current.write(x[index:index+tmp_len])
                        #print(out_file+" : "+str(out_file_size)+" : "+str(index)+" : "+str(index+tmp_len) + " : "+str(tmp_consumed) )
                        index += tmp_consumed
                        out_file_size -= tmp_consumed


def main(args=None):
    args = argparse.ArgumentParser(
    description ="""
zxd3 uses heuristics to try to diff two zips whose contents are *related* but
not named the same. Zip contents never hit the disc except when recreating the
target at the final step of -p.

It requires at least 256mb to be safe.""",
    epilog="""
In addition to the case where the contents are related but not named the same,
this tool exists because different files and implementations of zip can compress
in wildly different ways and orders so xdelta of zips is unlikely to give good
results.""",
    )
    group = args.add_mutually_exclusive_group()
    group.add_argument('-c', metavar=('source.zip', 'target.zip'), type=str, nargs=2, 
    help='create a patch that transforms source zip into target zip and extracts them. Patch will be named as source.zip.zxd3')
    group.add_argument('-c2', metavar=('source.zip', 'target.zip', 'patch.zxd3'), type=str, nargs=3,
    help='create a patch that transforms source zip into target zip and extracts them')
    group.add_argument('-p', metavar=('source.zip', 'patch.zxd3', 'out-dir'), type=str, nargs=3,
    help='apply a patch to source zip and extract contents of the patch to out-dir')
    args = args.parse_args()

    signal.signal(signal.SIGINT, signal.SIG_DFL) # Make Ctrl+C work
    if args.c:
        compress(args.c1[0], args.c1[1], args.c1[0]+".zxd3")
    elif args.c2:
        compress(args.c2[0], args.c2[1], args.c2[2])
    elif args.p:
        patch(args.p[0], args.p[1], args.p[2])

if __name__ == '__main__':
    main()

