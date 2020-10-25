# -*- coding: utf-8
#
# Copyright (C) 2019 Peter Rowlands <peter@pmrowla.com>
# Copyright (C) 2014 tinfoil <https://bitbucket.org/tinfoil/>
#
# This file is a part of pylivemaker.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with
# this program. If not, see <http://www.gnu.org/licenses/>.
"""LiveMaker archive/exe file module.

The `archive` module makes it possible to read and write LiveMaker archives (and
executables).

The API for `archive` behaves similary to Python's ``zipfile`` module,
with the exception that archives cannot be modified in-place (i.e. mode ``'a'``
is unavailable).

"""

import enum
import os.path
import shutil
import struct
import tempfile
import zlib
from io import open
from pathlib import Path, PureWindowsPath

import construct

from loguru import logger

from .exceptions import BadLiveMakerArchive, UnsupportedLiveMakerCompression
from .scramble import decrypt


class LMCompressType(enum.IntEnum):

    ZLIB = (0,)  # zlib compressed
    NONE = (1,)  # uncompressed (used for already compressed media types)
    ENCRYPTED = (2,)  # LiveMaker Pro encrypted + uncompressed
    ENCRYPTED_ZLIB = 3  # LiveMaker Pro encrypted + zlib compressed


SUPPORTED_COMPRESSIONS = [
    LMCompressType.NONE,
    LMCompressType.ZLIB,
    LMCompressType.ENCRYPTED,
    LMCompressType.ENCRYPTED_ZLIB,
]

# LM3 seed for TpRandom
LIVEMAKER3_XOR_SEED = 0x75D6EE39

# VF archive key array for TVrFile.ChecksumStream
VF_CHECKSUM_KEYS = [
    0x00000000,
    0x77073096,
    0xEE0E612C,
    0x990951BA,
    0x076DC419,
    0x706AF48F,
    0xE963A535,
    0x9E6495A3,
    0x0EDB8832,
    0x79DCB8A4,
    0xE0D5E91E,
    0x97D2D988,
    0x09B64C2B,
    0x7EB17CBD,
    0xE7B82D07,
    0x90BF1D91,
    0x1DB71064,
    0x6AB020F2,
    0xF3B97148,
    0x84BE41DE,
    0x1ADAD47D,
    0x6DDDE4EB,
    0xF4D4B551,
    0x83D385C7,
    0x136C9856,
    0x646BA8C0,
    0xFD62F97A,
    0x8A65C9EC,
    0x14015C4F,
    0x63066CD9,
    0xFA0F3D63,
    0x8D080DF5,
    0x3B6E20C8,
    0x4C69105E,
    0xD56041E4,
    0xA2677172,
    0x3C03E4D1,
    0x4B04D447,
    0xD20D85FD,
    0xA50AB56B,
    0x35B5A8FA,
    0x42B2986C,
    0xDBBBC9D6,
    0xACBCF940,
    0x32D86CE3,
    0x45DF5C75,
    0xDCD60DCF,
    0xABD13D59,
    0x26D930AC,
    0x51DE003A,
    0xC8D75180,
    0xBFD06116,
    0x21B4F4B5,
    0x56B3C423,
    0xCFBA9599,
    0xB8BDA50F,
    0x2802B89E,
    0x5F058808,
    0xC60CD9B2,
    0xB10BE924,
    0x2F6F7C87,
    0x58684C11,
    0xC1611DAB,
    0xB6662D3D,
    0x76DC4190,
    0x01DB7106,
    0x98D220BC,
    0xEFD5102A,
    0x71B18589,
    0x06B6B51F,
    0x9FBFE4A5,
    0xE8B8D433,
    0x7807C9A2,
    0x0F00F934,
    0x9609A88E,
    0xE10E9818,
    0x7F6A0DBB,
    0x086D3D2D,
    0x91646C97,
    0xE6635C01,
    0x6B6B51F4,
    0x1C6C6162,
    0x856530D8,
    0xF262004E,
    0x6C0695ED,
    0x1B01A57B,
    0x8208F4C1,
    0xF50FC457,
    0x65B0D9C6,
    0x12B7E950,
    0x8BBEB8EA,
    0xFCB9887C,
    0x62DD1DDF,
    0x15DA2D49,
    0x8CD37CF3,
    0xFBD44C65,
    0x4DB26158,
    0x3AB551CE,
    0xA3BC0074,
    0xD4BB30E2,
    0x4ADFA541,
    0x3DD895D7,
    0xA4D1C46D,
    0xD3D6F4FB,
    0x4369E96A,
    0x346ED9FC,
    0xAD678846,
    0xDA60B8D0,
    0x44042D73,
    0x33031DE5,
    0xAA0A4C5F,
    0xDD0D7CC9,
    0x5005713C,
    0x270241AA,
    0xBE0B1010,
    0xC90C2086,
    0x5768B525,
    0x206F85B3,
    0xB966D409,
    0xCE61E49F,
    0x5EDEF90E,
    0x29D9C998,
    0xB0D09822,
    0xC7D7A8B4,
    0x59B33D17,
    0x2EB40D81,
    0xB7BD5C3B,
    0xC0BA6CAD,
    0xEDB88320,
    0x9ABFB3B6,
    0x03B6E20C,
    0x74B1D29A,
    0xEAD54739,
    0x9DD277AF,
    0x04DB2615,
    0x73DC1683,
    0xE3630B12,
    0x94643B84,
    0x0D6D6A3E,
    0x7A6A5AA8,
    0xE40ECF0B,
    0x9309FF9D,
    0x0A00AE27,
    0x7D079EB1,
    0xF00F9344,
    0x8708A3D2,
    0x1E01F268,
    0x6906C2FE,
    0xF762575D,
    0x806567CB,
    0x196C3671,
    0x6E6B06E7,
    0xFED41B76,
    0x89D32BE0,
    0x10DA7A5A,
    0x67DD4ACC,
    0xF9B9DF6F,
    0x8EBEEFF9,
    0x17B7BE43,
    0x60B08ED5,
    0xD6D6A3E8,
    0xA1D1937E,
    0x38D8C2C4,
    0x4FDFF252,
    0xD1BB67F1,
    0xA6BC5767,
    0x3FB506DD,
    0x48B2364B,
    0xD80D2BDA,
    0xAF0A1B4C,
    0x36034AF6,
    0x41047A60,
    0xDF60EFC3,
    0xA867DF55,
    0x316E8EEF,
    0x4669BE79,
    0xCB61B38C,
    0xBC66831A,
    0x256FD2A0,
    0x5268E236,
    0xCC0C7795,
    0xBB0B4703,
    0x220216B9,
    0x5505262F,
    0xC5BA3BBE,
    0xB2BD0B28,
    0x2BB45A92,
    0x5CB36A04,
    0xC2D7FFA7,
    0xB5D0CF31,
    0x2CD99E8B,
    0x5BDEAE1D,
    0x9B64C2B0,
    0xEC63F226,
    0x756AA39C,
    0x026D930A,
    0x9C0906A9,
    0xEB0E363F,
    0x72076785,
    0x05005713,
    0x95BF4A82,
    0xE2B87A14,
    0x7BB12BAE,
    0x0CB61B38,
    0x92D28E9B,
    0xE5D5BE0D,
    0x7CDCEFB7,
    0x0BDBDF21,
    0x86D3D2D4,
    0xF1D4E242,
    0x68DDB3F8,
    0x1FDA836E,
    0x81BE16CD,
    0xF6B9265B,
    0x6FB077E1,
    0x18B74777,
    0x88085AE6,
    0xFF0F6A70,
    0x66063BCA,
    0x11010B5C,
    0x8F659EFF,
    0xF862AE69,
    0x616BFFD3,
    0x166CCF45,
    0xA00AE278,
    0xD70DD2EE,
    0x4E048354,
    0x3903B3C2,
    0xA7672661,
    0xD06016F7,
    0x4969474D,
    0x3E6E77DB,
    0xAED16A4A,
    0xD9D65ADC,
    0x40DF0B66,
    0x37D83BF0,
    0xA9BCAE53,
    0xDEBB9EC5,
    0x47B2CF7F,
    0x30B5FFE9,
    0xBDBDF21C,
    0xCABAC28A,
    0x53B39330,
    0x24B4A3A6,
    0xBAD03605,
    0xCDD70693,
    0x54DE5729,
    0x23D967BF,
    0xB3667A2E,
    0xC4614AB8,
    0x5D681B02,
    0x2A6F2B94,
    0xB40BBE37,
    0xC30C8EA1,
    0x5A05DF1B,
    0x2D02EF8D,
]

MIN_ARCHIVE_VERSION = 100
DEFAULT_VERSION = 102

# Max size of one split archive part (1GB)
SPLIT_ARCHIVE_PART_SIZE = 1073741824


class LMObfuscator(object):
    """Class for (de)obfuscating LiveMaker directory fields.

    Note:
        RE'd from TTpRandom class in LiveMaker code.

    """

    def __init__(self, seed=LIVEMAKER3_XOR_SEED):
        self.keystream = self._keystream(seed)

    @classmethod
    def _keystream(cls, seed=LIVEMAKER3_XOR_SEED):
        """xor keystream generator used for obfuscating archive filenames and offets.

        Yields (int): The next XOR value.

        """
        key = 0
        while True:
            key = ((key << 2) + key + seed) & 0xFFFFFFFF
            yield key

    def transform_bytes(self, data):
        return construct.integers2bytes((b ^ (next(self.keystream) & 0xFF)) for b in construct.iterateints(data))

    def transform_int(self, data):
        key = next(self.keystream)
        data = [(b ^ ((key >> (8 * i)) & 0xFF)) for i, b in enumerate(construct.iterateints(data))]
        return construct.integers2bytes(data)

    def transform_int_high(self, data):
        # special case for re-encoding high part of offsets
        # LiveMaker always only outputs 0 or 0xffffffff depending on if high
        # bit ends up set
        key = next(self.keystream)
        data = [(b ^ ((key >> (8 * i)) & 0xFF)) for i, b in enumerate(construct.iterateints(data))]
        if data[3] & 0x80:
            data = [0xFF, 0xFF, 0xFF, 0xFF]
        else:
            data = [0, 0, 0, 0]
        return construct.integers2bytes(data)


class _LMArchiveVersionValidator(construct.Validator):
    """Construct validator for supported LiveMaker archive versions."""

    def _validate(self, obj, ctx, path):
        return obj >= MIN_ARCHIVE_VERSION

    def _decode(self, obj, ctx, path):
        if not self._validate(obj, ctx, path):
            raise construct.ValidationError("Unsupported LiveMaker archive version: {}".format(obj))
        return obj


class LMArchiveDirectory(object):
    """Class for handling parsing and writing archive directories.

    LiveMaker archive format is::

        Directory Header:
            16-bit "vf" signature
            32-bit uint version
            32-bit uint count

        Filenames (list with length <count> entries):
            32-bit uint prefixed pascal strings (CP932 (MS Shift-JIS) encoded)

        Offsets (list with length <file_count> + 1):
            32-bit uint offset_low
            32-bit uint offset_high

        Compression flags (list with length <file_count>)
            8-bit uint compression method

        Unknown list (list length <file_count>)
            32-bit uint unk1

        Checksums - (list length <file_count>)
            32-bit uint checksum

        Encryption flags 0 if not encrypted (list length <file_count>)
            8-bit uint encrypt_flag

        File data
            ...

    Note:
        LiveMaker3 mangles filenames and offsets by XOR'ing them with a fixed keystream.
        Individual files may also be encrypted/obfuscated, this is specified by the compression flags.

        Offsets are actually 64-bit long long, but they are stored as two separate 32-bit integers.

        The extra offset entry is used to calculate the (compressed) size of the final file.

        If ``encrypt_flag`` is zero, ``checksum`` is the checksum of the compressed file data.
            If ``encrypt_flag`` is nonzero ``checksum`` is the checksum of the uncompressed and
            decrypted file data.

        RE'd from TVrFileCollection classes in LiveMaker code.

    """

    @classmethod
    def struct(cls):
        return construct.Struct(
            "signature" / construct.Const(b"vf"),
            "version" / _LMArchiveVersionValidator(construct.Int32ul),
            "count" / construct.Int32ul,
            "filenames"
            / construct.Array(
                construct.this.count,
                construct.IfThenElse(
                    construct.this.version >= 100,
                    construct.Prefixed(
                        construct.Int32ul,
                        construct.Transformed(
                            construct.GreedyString("cp932"),
                            LMObfuscator().transform_bytes,
                            None,
                            LMObfuscator().transform_bytes,
                            None,
                        ),
                    ),
                    construct.PascalString(construct.Int32ul, "cp932"),
                ),
            ),
            "offsets"
            / construct.Array(
                construct.this.count + 1,
                construct.Struct(
                    "offset_low"
                    / construct.IfThenElse(
                        construct.this._.version >= 100,
                        construct.Transformed(
                            construct.Int32ul,
                            LMObfuscator().transform_int,
                            4,
                            LMObfuscator().transform_int,
                            4,
                        ),
                        construct.Int32ul,
                    ),
                    # offset_high always 0 if ver < 101
                    "offset_high"
                    / construct.IfThenElse(
                        construct.this._.version >= 101,
                        construct.Transformed(
                            construct.Int32ul,
                            LMObfuscator().transform_int,
                            4,
                            LMObfuscator().transform_int_high,
                            4,
                        ),
                        construct.Int32ul,
                    ),
                ),
            ),
            "compress_types" / construct.Array(construct.this.count, construct.Enum(construct.Byte, LMCompressType)),
            "unk1s"
            / construct.Array(
                construct.this.count,
                # construct.Transformed(
                #     construct.Int32ul,
                #     LMObfuscator().transform_int,
                #     4,
                #     LMObfuscator().transform_int,
                #     4,
                # ),
                construct.Int32ul,
            ),
            "checksums"
            / construct.Array(
                construct.this.count,
                construct.Int32ul,
            ),
            "encrypt_flags"
            / construct.Array(
                construct.this.count,
                construct.Byte,
            ),
        )

    @classmethod
    def make_offset(cls, obj):
        """Join split offset into one 64-bit unsigned offset."""
        return ((obj.offset_high & 0x80000000) << 32) | obj.offset_low

    @classmethod
    def split_offset(cls, offset):
        """Split an offset into the expected components for writing to an archive."""
        return {"offset_low": offset & 0xFFFFFFFF, "offset_high": (offset >> 32) << 31}

    @classmethod
    def directory_size(cls, version, filenames=[]):
        """Return the size of a directory containing `filenames`."""
        # we have to build an empty dir since construct sizeof() only works if
        # a struct has a fixed size
        count = len(filenames)
        directory = {
            "version": version,
            "count": count,
            "filenames": filenames,
            "offsets": [cls.split_offset(0)] * (count + 1),
            "compress_types": ["NONE"] * count,
            "unk1s": [0] * count,
            "checksums": [0] * count,
            "encrypt_flags": [0] * count,
        }
        return len(cls.struct().build(directory))

    @classmethod
    def checksum(cls, data):
        """Compute a VF archive checksum for the specified data.

        RE'd from TVrFile.ChecksumStream().

        Args:
            data (bytes): The data to checksum

        """
        csum = 0xFFFFFFFF
        for c in data:
            x = (csum & 0xFF) ^ c
            x = VF_CHECKSUM_KEYS[x]
            csum = (csum >> 8) ^ x
        return csum ^ 0xFFFFFFFF


class LMArchive(object):
    """Provide interface to a LiveMaker archive (or exe).

    Behaves in the same manner as Python ``tarfile.TarFile`` or ``zipfile.ZipFile``.
    Can be used inside a Python ``with`` statement (in the same way as zip/tar files).

    Args:
        name: Pathname for the archive. `name` can be a string or path-like object.
            If omitted, `fp` must be specified.
        mode: Either ``'r'`` to read from an existing archive or ``'w'`` to create a new file
            (overwriting an existing one). Defaults to ``'r'``.
        fp: If `fileobj` is given, it will be used for reading and writing data.
            If it can be determined, `mode` will be overridden by `fp`'s mode. `fileobj`
            will be used from position 0.
        exe: Pathname for LiveMaker executable (``.exe``) file. If `exe` is given and
            `mode` is ``w``, the output file will be an executable with the archive
            appended to the end (i.e. a LiveMaker ``.exe`` file). If `exe` is not given,
            the output file will be a standalone archive (i.e. a LiveMaker ``.dat`` file).
            `exe` does nothing when opening a file for reading.
        split: If opening in write mode and `split` is ``True``, the archive data will be split
            into smaller files across 1GB boundaries. `split` has no effect in read mode or when
            writing an executable archive.
        version: Archive version, only applies to write mode.

    Note:
        `fp` is not closed when `LiveMakerArchive` is closed.

        ``'a'`` is an invalid `mode` for `LiveMakerArchive`. Archives cannot be modified
        in place, to patch an existing archive, you must write to a new file.

        When opened in write mode, the output archive file will not be written until
        `LMArchive.close()` is called. As entries are added to the archive, they will
        be written to a temporary file. Upon calling `close()`, the exe (if it exists)
        and archive header will be written to the output file, then the temporary file
        will be copied to the end of the output file.

    """

    def __init__(self, name=None, mode="r", fp=None, exe=None, split=False, version=DEFAULT_VERSION):
        self.closed = True
        if not name and not fp:
            raise ValueError("Nothing to open")
        modes = {"r": "rb", "w": "wb"}
        if mode not in modes:
            raise ValueError("mode must be 'r' or 'w'")
        self.mode = mode
        self._mode = modes[mode]

        if not fp:
            fp = open(name, self._mode)
            self._extfp = False
        else:
            if name is None and hasattr(fp, "name") and isinstance(fp.name, (str, bytes)):
                name = fp.name
            if hasattr(fp, "mode"):
                self._mode = fp.mode
            self._extfp = True
        self.fp = fp
        self.closed = False

        self.name = str(Path(name).resolve())
        root, ext = os.path.splitext(self.name)

        self.filelist = []
        self.name_info = {}

        try:
            if mode == "w":
                self._read_fps = []
                if exe:
                    self.exefp = open(exe, "rb")
                    self.is_exe = True
                    self.is_split = False
                    self.has_ext = False
                else:
                    self.is_exe = False
                    if split:
                        self.is_split = True
                        self._split_base = root
                        self._split_files = set([self.name])
                        if ext.lower() not in [".dat", ".ext"]:
                            logger.warning("Writing split archive index without .dat or .ext file extension.")
                        elif ext.lower() == ".ext":
                            self.has_ext = True
                        else:
                            self.has_ext = False
                    else:
                        self.is_split = False
                        self.has_ext = False
                    self.exefp = None
                self.tmpfp = tempfile.TemporaryFile()
                self.version = version
            else:
                self.exefp = None
                self.is_exe = False
                self.tmpfp = None
                self._read_fps = []
                savepos = self.fp.tell()
                self.archive_offset = self._find_archive_offset()
                self._parse_directory()
                if ext.lower() in [".dat", ".ext"]:
                    self.is_split = True
                    self._split_base = root
                    self._split_files = set([self.name])
                    if ext.lower() == ".ext":
                        self.has_ext = True
                        dat_file = "{}.dat".format(self._split_base)
                        if not os.path.isfile(dat_file):
                            raise BadLiveMakerArchive(
                                "Could not find (.dat) data file for split archive index {}.".format(self.name)
                            )
                        self._split_files.add(dat_file)
                        self._read_fps.append(open(dat_file, self._mode))
                    else:
                        self.has_ext = False
                        self._read_fps.append(self.fp)
                    for i in range(1, 100):
                        dat_file = "{}.{:03}".format(self._split_base, i)
                        if os.path.isfile(dat_file):
                            self._read_fps.append(open(dat_file, self._mode))
                            self._split_files.add(dat_file)
                else:
                    self.is_split = False
                    self.has_ext = False
        except Exception as e:
            if self._extfp:
                self.fp.seek(savepos)
            else:
                if self._read_fps:
                    for fp in self._read_fps:
                        if fp != self.fp:
                            fp.close()
                self.fp.close()
            self.closed = True
            raise e

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def __del__(self):
        self.close()

    def close(self):
        """Close the archive file.

        When an archive is opened in write mode, `close()` must be called before exiting your program
        or else the archive will not actually be written.

        """
        if self.closed:
            return

        try:
            if self.mode == "w":
                self._write_exe()
                self._write_directory()
                self._write_archive()
                self._write_trailer()
        finally:
            if self.exefp:
                self.exefp.close()
            if self.tmpfp:
                self.tmpfp.close()
            if self._read_fps:
                for fp in self._read_fps:
                    if fp != self.fp:
                        fp.close()
            if not self._extfp:
                self.fp.close()
            self.closed = True

    def namelist(self):
        """Return a list of archive entries by name."""
        return sorted(self.name_info.keys())

    def infolist(self):
        """Return a containing a `LMArchiveInfo` object for each entry in the archive."""
        return self.filelist

    def getinfo(self, name):
        """Return a `LMArchiveInfo` object for the entry with the specified name.

        Raises:
            KeyError: If `name` is not an entry in the archive.

        """
        info = self.name_info.get(name)
        if info is None:
            raise KeyError("{} does not exist in archive.".format(name))
        return info

    def list(self):
        """Print a list of archive entries to stdout."""
        print(self.name)
        print("-------- ------ -------- -------- ------- ------")
        print(" Length   Mode    unk1    Chksum   Flags   Name")
        print("-------- ------ -------- -------- ------- ------")
        for info in self.infolist():
            print(
                "{:8} {:6} {:08x} {:08x} {:02x} {}".format(
                    info.compressed_size,
                    info.compress_type.name,
                    info.unk1,
                    info.checksum,
                    info.encrypt_flag,
                    info.name,
                )
            )

    def _find_archive_offset(self):
        """Find offset for the start of the archive."""
        self.fp.seek(0)
        if self.fp.read(2) == b"MZ":
            # File is an MS executable
            self.is_exe = True
            self.fp.seek(-2, 2)
            # Check for 'lv' trailer
            if self.fp.read(2) != b"lv":
                raise BadLiveMakerArchive("EXE does not contain a LiveMaker archive.")
            # Read offset for start of archive
            self.fp.seek(-6, 2)
            (offset,) = struct.unpack("<I", self.fp.read(4))
            return offset
        else:
            self.is_exe = False
            return 0

    def _parse_directory(self):
        """Parse the file index for this archive."""
        self.fp.seek(self.archive_offset)
        try:
            directory = LMArchiveDirectory.struct().parse_stream(self.fp)
        except construct.ConstructError as e:
            raise BadLiveMakerArchive("Failed to parse VF directory: {}".format(e))
        self.version = directory.version
        filenames = directory.filenames
        offsets = directory.offsets
        unk1s = directory.unk1s
        checksums = directory.checksums
        encrypt_flags = directory.encrypt_flags
        compress_types = directory.compress_types
        for i, name in enumerate(filenames):
            info = LMArchiveInfo(name)
            info._offset = LMArchiveDirectory.make_offset(offsets[i])
            next_offset = LMArchiveDirectory.make_offset(offsets[i + 1])
            info.compressed_size = next_offset - info._offset
            info.compress_type = LMCompressType(int(compress_types[i]))
            info.unk1 = unk1s[i]
            info.checksum = checksums[i]
            info.encrypt_flag = encrypt_flags[i]
            self.filelist.append(info)
            self.name_info[name] = info

    def _extract(self, entry, output_path):
        """Extract the specified entry."""
        if self.closed:
            raise ValueError("Archive is already closed.")
        if self.mode != "r":
            raise ValueError("Cannot extract entry from archive which is open for writing.")
        if not isinstance(entry, LMArchiveInfo):
            entry = self.getinfo(entry)
        path = Path.joinpath(output_path, entry.path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.read(entry)
        with path.open("wb") as f:
            f.write(data)

    def extract(self, name, path=None):
        """Extract the specified entry from the archive to the current working directory.

        Args:
            name (str, :class:`LMArchiveInfo`): The entry to extract, can be either it's full name or
                a `LMArchiveInfo` object.
            path: If given, the `path` will be used instead of the current working directory.

        Raises:
            UnsupportedLiveMakerCompression: If the specified entry uses an unsupported
                compression method.

        """
        if path is not None:
            path = Path(path)
        else:
            path = Path.cwd()
        self._extract(name, path)

    def extractall(self, path=None, entries=None, allow_unsupported=False):
        """Extract all entries in this archive to the current working directory.

        Args:
            path: If `path` is given, it will be used instead of the current working directory.
            entries: Optional value that must be a subset of the list returned by `namelist()`
                or `infolist()`.
            allow_unsupported: If `True`, any files which are compressed with an unsupported
                method will be silently ignored. If `False`, an exception will be raised when
                trying to extract any files which use unsupported compression methods.

        Raises:
            UnsupportedLiveMakerCompression

        """
        if path is not None:
            path = Path(path)
        else:
            path = Path.cwd()
        if entries is None:
            entries = self.infolist()
        for name in entries:
            try:
                self._extract(name, path)
            except UnsupportedLiveMakerCompression as e:
                if not allow_unsupported:
                    raise e
                logger.warning("Skipping encrypted file {}".format(e))

    def read(self, name, decompress=True, skip_checksum=True):
        """Return the bytes of the specified file in the archive.

        The archive must be open for reading.

        Args:
            name: Either the name of a file in the archive or a `LMArchiveInfo` object.
            decompress: If ``True`` the returned bytes will be decompressed. If ``False``
                the original compressed entry data will be returned.
            skip_checksum: If ``True`` the file checksum will not be verified. If ``False``
                the checksum will be verified. If the checksum does not match, the file will
                still be extracted, but a warning will be logged.

        Raises:
            UnsupportedLiveMakerCompression: If `decompress` is ``True`` and the
                specified entry uses an unsupported compression method.

        """
        if self.closed:
            raise ValueError("Archive is already closed.")
        if self.mode != "r":
            raise ValueError("Cannot read entry in archive which is open for writing.")
        if isinstance(name, LMArchiveInfo):
            info = name
        else:
            info = self.getinfo(name)
        if decompress and info.compress_type not in SUPPORTED_COMPRESSIONS:
            raise UnsupportedLiveMakerCompression("{} is unsupported".format(info.compress_type))
        if self._read_fps:
            # archive data is split on 1GB (1024 * 1024 * 1024 bytes) boundaries
            # start reading from whichever data file contains the start of
            # this node, and then continue reading across boundary as needed
            offset = self.archive_offset + info._offset
            data = b""
            while len(data) < info.compressed_size:
                bytes_needed = info.compressed_size - len(data)
                fp = self._read_fps[offset // SPLIT_ARCHIVE_PART_SIZE]
                fp.seek(offset % SPLIT_ARCHIVE_PART_SIZE)
                tmp = fp.read(bytes_needed)
                data += tmp
                offset += len(tmp)
        else:
            fp = self.fp
            fp.seek(self.archive_offset + info._offset)
            data = self.fp.read(info.compressed_size)
        if not skip_checksum and info.checksum is not None:
            if info.checksum != LMArchiveDirectory.checksum(data):
                logger.warning("Bad checksum for file {}.".format(info.name))
        if decompress:
            if info.compress_type in (LMCompressType.ENCRYPTED, LMCompressType.ENCRYPTED_ZLIB):
                data = decrypt(data)

            if info.compress_type in (LMCompressType.ZLIB, LMCompressType.ENCRYPTED_ZLIB):
                try:
                    data = zlib.decompress(data)
                except zlib.error as e:
                    raise UnsupportedLiveMakerCompression(str(e))
        return data

    def read_exe(self):
        """Return the exe bytes for this archive.

        Raises:
            ValueError: If this archive is not part of a LiveMaker executable
                (i.e. it is a ``.dat`` file).

        """
        if self.closed:
            raise ValueError("Archive is already closed.")
        if self.mode != "r":
            raise ValueError("Cannot read exe from archive which is open for writing.")
        if not self.is_exe:
            raise ValueError("Archive is not part of a LiveMaker excecutable.")
        self.fp.seek(0)
        return self.fp.read(self.archive_offset)

    def write(self, filename, arcname=None, compress_type=None, unk1=None):
        """Write the file named `filename` into the archive.

        Args:
            filename: File to write into archive.
            arcname: If given, the archive file entry will be named `arcname`.
                By default, `arcname` will be the same as `filename`,
                but with any drive letter and leading path separators removed.
                Posix paths will be replaced with equivalent Windows paths.
            compress_type (`LMCompressType`): If given, the file will be compressed
                with the specified method (defaults to uncompressed for files < 5MB
                in size, and zlib compressed for files >= 5MB).

        Returns:
            The number of (compressed) bytes written.

        Raises:
            FileExistsError: If an entry matching `arcname` already exists in this archive.
            UnsupportedLiveMakerCompression: If the `compress_type` is unsupported.

        """
        if self.closed:
            raise ValueError("Archive is already closed.")
        if self.mode != "w":
            raise ValueError("Cannot write to archive opened for reading.")
        if arcname is None:
            arcpath = PureWindowsPath(filename)
        else:
            arcpath = PureWindowsPath(arcname)
        # strip drive and leading pathsep
        name = str(arcpath.relative_to(arcpath.anchor))
        if name in self.name_info:
            raise FileExistsError("{} already exists in this archive.".format(name))
        if compress_type is not None and compress_type not in SUPPORTED_COMPRESSIONS:
            raise UnsupportedLiveMakerCompression("{} is not supported.".format(compress_type))
        info = LMArchiveInfo(name)
        with open(filename, "rb") as f:
            data = f.read()
        if compress_type is None:
            if len(data) >= 0x500000:
                compress_type = LMCompressType.ZLIB
            else:
                compress_type = LMCompressType.NONE
        if compress_type == LMCompressType.ZLIB:
            data = zlib.compress(data)
        if unk1 is not None:
            info.unk1 = unk1
        info.compress_type = compress_type
        info.compressed_size = len(data)
        info.checksum = LMArchiveDirectory.checksum(data)
        info._offset = self.tmpfp.tell()
        self.tmpfp.write(data)
        self.filelist.append(info)
        self.name_info[name] = info
        return info.compressed_size

    def writebytes(self, arcname, data, compress_type=None, skip_checksum=True):
        """Write a raw (already compressed) file into the archive.

        This method can be used to copy compressed data from an
        old archive into a new one without needing to do any
        intermediate extraction. This may be useful for copying
        encrypted files from one archive into another.

        Args:
            arcname: The archive entry name (or `LMArchiveInfo` object).
            data (bytes): The contents of `arcname`. `data` must be a bytes
                instance, not a str instance. `data` must be compressed using
                the compression type specified in `compress_type` or the `arcname`
                `LMArchiveInfo` object.
            compress_type: The compression type for the newly created archive
                entry will be set to this value. If `arcname` is a string, `compress_type`
                must be explicitly set. `compress_type` can be omitted if `arcname` is an
                `LMArchiveInfo` object, in which case compression type will be read from
                the info object.
            skip_checksum: If ``True`` and `arcname` is a `LMArchiveInfo` object, checksum
                for `data` will not be calculated, and will be copied from `arcname`.

        Returns:
            The number of bytes written.

        Raises:
            FileExistsError: If an entry matching `arcname` already exists in this archive.

        """
        if self.closed:
            raise ValueError("Archive is already closed.")
        if self.mode != "w":
            raise ValueError("Cannot write to archive opened for reading.")
        if isinstance(arcname, LMArchiveInfo):
            info = LMArchiveInfo(arcname.name)
            info.compress_type = arcname.compress_type
            info.unk1 = arcname.unk1
            if skip_checksum:
                info.checksum = arcname.checksum
            info.encrypt_flag = arcname.encrypt_flag
        else:
            if compress_type is None:
                raise ValueError("Compression type must be specified")
            info = LMArchiveInfo(arcname)
            info.compress_type = compress_type
        if info.name in self.name_info:
            raise FileExistsError("{} already exists in this archive.".format(arcname))
        info.compressed_size = len(data)
        if info.checksum is None:
            info.checksum = LMArchiveDirectory.checksum(data)
        info._offset = self.tmpfp.tell()
        self.tmpfp.write(data)
        self.filelist.append(info)
        self.name_info[info.name] = info
        return info.compressed_size

    def _write_exe(self):
        if self.is_exe and self.exefp:
            self.fp.write(self.exefp.read())

    def _write_directory(self):
        directory = {
            "version": self.version,
            "count": len(self.filelist),
            "filenames": [],
            "offsets": [],
            "compress_types": [],
            "unk1s": [],
            "checksums": [],
            "encrypt_flags": [],
        }
        self.archive_offset = archive_offset = self.fp.tell()
        directory_size = LMArchiveDirectory.directory_size(self.version, self.name_info.keys())
        filenames = directory["filenames"]
        offsets = directory["offsets"]
        compress_types = directory["compress_types"]
        unk1s = directory["unk1s"]
        checksums = directory["checksums"]
        encrypt_flags = directory["encrypt_flags"]
        for info in self.filelist:
            filenames.append(info.name)
            # info offset will be the offset of this entry in the temporary
            # file (i.e. starting at 0). archive offsets need to start from the
            # end of the directory.
            offset = info._offset
            if not self.is_split or not self.has_ext:
                offset = info._offset + directory_size
            offsets.append(LMArchiveDirectory.split_offset(offset))
            compress_types.append(info.compress_type)
            unk1s.append(info.unk1)
            checksums.append(info.checksum)
            encrypt_flags.append(info.encrypt_flag)
        last_entry = self.filelist[-1]
        if last_entry is not None:
            offset = last_entry._offset + last_entry.compressed_size
            if not self.is_split or not self.has_ext:
                offset += directory_size
            offsets.append(LMArchiveDirectory.split_offset(offset))
        else:
            # handle empty archive
            offsets.append(LMArchiveDirectory.split_offset(archive_offset))
        data = LMArchiveDirectory.struct().build(directory)
        self.fp.write(data)

    def _write_archive(self):
        # copy data from temp file into final archive
        if self.is_split:
            self.tmpfp.seek(0, 2)
            data_offset = self.fp.tell()
            if data_offset > SPLIT_ARCHIVE_PART_SIZE:
                raise BadLiveMakerArchive("Cannot generate split archive with exe+directory size > 1GB")
            if self.has_ext:
                total_size = self.tmpfp.tell()
                extra_files = total_size // SPLIT_ARCHIVE_PART_SIZE
            else:
                total_size = data_offset + self.tmpfp.tell()
                extra_files = total_size // SPLIT_ARCHIVE_PART_SIZE
            if total_size and (total_size % SPLIT_ARCHIVE_PART_SIZE) == 0:
                extra_files -= 1
            self.tmpfp.seek(0)
            if self.has_ext:
                dat_file = "{}.dat".format(self._split_base)
                with open(dat_file, self._mode) as fp:
                    fp.write(self.tmpfp.read(SPLIT_ARCHIVE_PART_SIZE))
                self._split_files.add(dat_file)
            else:
                self.fp.write(self.tmpfp.read(SPLIT_ARCHIVE_PART_SIZE - data_offset))
            for i in range(1, extra_files + 1):
                dat_file = "{}.{:03}".format(self._split_base, i)
                with open(dat_file, self._mode) as fp:
                    fp.write(self.tmpfp.read(SPLIT_ARCHIVE_PART_SIZE))
                self._split_files.add(dat_file)
        else:
            self.tmpfp.seek(0)
            shutil.copyfileobj(self.tmpfp, self.fp)

    def _write_trailer(self):
        if not self.is_split:
            data = struct.pack("<I", self.archive_offset)
            self.fp.write(data)
            self.fp.write(b"lv")


class LMArchiveInfo(object):
    """An entry (file) contained in a LiveMaker archive.

    Attributes:
        name (str): Filename.
        compress_type (`LMCompressType`): Compression type.
        compressed_size (int): Compressed file size in bytes.
        checksum: VF checksum for the compressed data.
            See `LMArchiveDirectory.checksum()` for how checksum is calculated.
        encrypt_flag: Only used for LiveMaker Pro encrypted files.

    """

    def __init__(self, name=""):
        self.name = name
        self._offset = 0
        self.compress_type = LMCompressType.NONE
        self.compressed_size = 0
        # fairly sure these are supposed to be some sort of checksum but as
        # far as I can tell a LiveNovel game exe never actually verifies them??
        self.unk1 = 0
        self.checksum = None
        self.encrypt_flag = 0

    def __str__(self):
        return self.name

    @property
    def path(self):
        return PureWindowsPath(self.name)
