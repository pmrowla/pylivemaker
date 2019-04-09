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

Note:
    Reading (and writing) files which are encrypted via LiveMaker Pro is not
    supported, but any non-encrypted files from a LiveMaker Pro archive can
    be extracted.

"""

import enum
import logging
import shutil
import struct
import tempfile
import zlib
from io import open
from pathlib import Path, PureWindowsPath

import construct

from .exceptions import BadLiveMakerArchive, UnsupportedLiveMakerCompression


log = logging.getLogger(__name__)


class LMCompressType(enum.IntEnum):

    ZLIB = 0,               # zlib compressed
    NONE = 1,               # uncompressed (used for already compressed media types)
    ENCRYPTED = 2,          # LiveMaker Pro encrypted + uncompressed
    ENCRYPTED_ZLIB = 3      # LiveMaker Pro encrypted + zlib compressed


SUPPORTED_COMPRESSIONS = [
    LMCompressType.NONE,
    LMCompressType.ZLIB
]

# LM3 seed for TpRandom
LIVEMAKER3_XOR_SEED = 0x75d6ee39

# VF archive key array for TVrFile.ChecksumStream
VF_CHECKSUM_KEYS = [
    0x00000000, 0x77073096, 0xee0e612c, 0x990951ba,
    0x076dc419, 0x706af48f, 0xe963a535, 0x9e6495a3,
    0x0edb8832, 0x79dcb8a4, 0xe0d5e91e, 0x97d2d988,
    0x09b64c2b, 0x7eb17cbd, 0xe7b82d07, 0x90bf1d91,
    0x1db71064, 0x6ab020f2, 0xf3b97148, 0x84be41de,
    0x1adad47d, 0x6ddde4eb, 0xf4d4b551, 0x83d385c7,
    0x136c9856, 0x646ba8c0, 0xfd62f97a, 0x8a65c9ec,
    0x14015c4f, 0x63066cd9, 0xfa0f3d63, 0x8d080df5,
    0x3b6e20c8, 0x4c69105e, 0xd56041e4, 0xa2677172,
    0x3c03e4d1, 0x4b04d447, 0xd20d85fd, 0xa50ab56b,
    0x35b5a8fa, 0x42b2986c, 0xdbbbc9d6, 0xacbcf940,
    0x32d86ce3, 0x45df5c75, 0xdcd60dcf, 0xabd13d59,
    0x26d930ac, 0x51de003a, 0xc8d75180, 0xbfd06116,
    0x21b4f4b5, 0x56b3c423, 0xcfba9599, 0xb8bda50f,
    0x2802b89e, 0x5f058808, 0xc60cd9b2, 0xb10be924,
    0x2f6f7c87, 0x58684c11, 0xc1611dab, 0xb6662d3d,
    0x76dc4190, 0x01db7106, 0x98d220bc, 0xefd5102a,
    0x71b18589, 0x06b6b51f, 0x9fbfe4a5, 0xe8b8d433,
    0x7807c9a2, 0x0f00f934, 0x9609a88e, 0xe10e9818,
    0x7f6a0dbb, 0x086d3d2d, 0x91646c97, 0xe6635c01,
    0x6b6b51f4, 0x1c6c6162, 0x856530d8, 0xf262004e,
    0x6c0695ed, 0x1b01a57b, 0x8208f4c1, 0xf50fc457,
    0x65b0d9c6, 0x12b7e950, 0x8bbeb8ea, 0xfcb9887c,
    0x62dd1ddf, 0x15da2d49, 0x8cd37cf3, 0xfbd44c65,
    0x4db26158, 0x3ab551ce, 0xa3bc0074, 0xd4bb30e2,
    0x4adfa541, 0x3dd895d7, 0xa4d1c46d, 0xd3d6f4fb,
    0x4369e96a, 0x346ed9fc, 0xad678846, 0xda60b8d0,
    0x44042d73, 0x33031de5, 0xaa0a4c5f, 0xdd0d7cc9,
    0x5005713c, 0x270241aa, 0xbe0b1010, 0xc90c2086,
    0x5768b525, 0x206f85b3, 0xb966d409, 0xce61e49f,
    0x5edef90e, 0x29d9c998, 0xb0d09822, 0xc7d7a8b4,
    0x59b33d17, 0x2eb40d81, 0xb7bd5c3b, 0xc0ba6cad,
    0xedb88320, 0x9abfb3b6, 0x03b6e20c, 0x74b1d29a,
    0xead54739, 0x9dd277af, 0x04db2615, 0x73dc1683,
    0xe3630b12, 0x94643b84, 0x0d6d6a3e, 0x7a6a5aa8,
    0xe40ecf0b, 0x9309ff9d, 0x0a00ae27, 0x7d079eb1,
    0xf00f9344, 0x8708a3d2, 0x1e01f268, 0x6906c2fe,
    0xf762575d, 0x806567cb, 0x196c3671, 0x6e6b06e7,
    0xfed41b76, 0x89d32be0, 0x10da7a5a, 0x67dd4acc,
    0xf9b9df6f, 0x8ebeeff9, 0x17b7be43, 0x60b08ed5,
    0xd6d6a3e8, 0xa1d1937e, 0x38d8c2c4, 0x4fdff252,
    0xd1bb67f1, 0xa6bc5767, 0x3fb506dd, 0x48b2364b,
    0xd80d2bda, 0xaf0a1b4c, 0x36034af6, 0x41047a60,
    0xdf60efc3, 0xa867df55, 0x316e8eef, 0x4669be79,
    0xcb61b38c, 0xbc66831a, 0x256fd2a0, 0x5268e236,
    0xcc0c7795, 0xbb0b4703, 0x220216b9, 0x5505262f,
    0xc5ba3bbe, 0xb2bd0b28, 0x2bb45a92, 0x5cb36a04,
    0xc2d7ffa7, 0xb5d0cf31, 0x2cd99e8b, 0x5bdeae1d,
    0x9b64c2b0, 0xec63f226, 0x756aa39c, 0x026d930a,
    0x9c0906a9, 0xeb0e363f, 0x72076785, 0x05005713,
    0x95bf4a82, 0xe2b87a14, 0x7bb12bae, 0x0cb61b38,
    0x92d28e9b, 0xe5d5be0d, 0x7cdcefb7, 0x0bdbdf21,
    0x86d3d2d4, 0xf1d4e242, 0x68ddb3f8, 0x1fda836e,
    0x81be16cd, 0xf6b9265b, 0x6fb077e1, 0x18b74777,
    0x88085ae6, 0xff0f6a70, 0x66063bca, 0x11010b5c,
    0x8f659eff, 0xf862ae69, 0x616bffd3, 0x166ccf45,
    0xa00ae278, 0xd70dd2ee, 0x4e048354, 0x3903b3c2,
    0xa7672661, 0xd06016f7, 0x4969474d, 0x3e6e77db,
    0xaed16a4a, 0xd9d65adc, 0x40df0b66, 0x37d83bf0,
    0xa9bcae53, 0xdebb9ec5, 0x47b2cf7f, 0x30b5ffe9,
    0xbdbdf21c, 0xcabac28a, 0x53b39330, 0x24b4a3a6,
    0xbad03605, 0xcdd70693, 0x54de5729, 0x23d967bf,
    0xb3667a2e, 0xc4614ab8, 0x5d681b02, 0x2a6f2b94,
    0xb40bbe37, 0xc30c8ea1, 0x5a05df1b, 0x2d02ef8d,
]

MIN_ARCHIVE_VERSION = 100
DEFAULT_VERSION = 102


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
            key = ((key << 2) + key + seed) & 0xffffffff
            yield key

    def transform_bytes(self, data):
        return construct.integers2bytes((b ^ (next(self.keystream) & 0xff)) for b in construct.iterateints(data))

    def transform_int(self, data):
        key = next(self.keystream)
        data = [(b ^ ((key >> (8 * i)) & 0xff)) for i, b in enumerate(construct.iterateints(data))]
        return construct.integers2bytes(data)

    def transform_int_high(self, data):
        # special case for re-encoding high part of offsets
        # LiveMaker always only outputs 0 or 0xffffffff depending on if high
        # bit ends up set
        key = next(self.keystream)
        data = [(b ^ ((key >> (8 * i)) & 0xff)) for i, b in enumerate(construct.iterateints(data))]
        if data[3] & 0x80:
            data = [0xff, 0xff, 0xff, 0xff]
        else:
            data = [0, 0, 0, 0]
        return construct.integers2bytes(data)


class _LMArchiveVersionValidator(construct.Validator):
    """Construct validator for supported LiveMaker archive versions."""

    def _validate(self, obj, ctx, path):
        return obj >= MIN_ARCHIVE_VERSION

    def _decode(self, obj, ctx, path):
        if not self._validate(obj, ctx, path):
            raise construct.ValidationError('Unsupported LiveMaker archive version: {}'.format(obj))
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
            "filenames" / construct.Array(
                construct.this.count,
                construct.IfThenElse(
                    construct.this.version >= 100,
                    construct.Prefixed(
                        construct.Int32ul,
                        construct.Transformed(
                            construct.GreedyString('cp932'),
                            LMObfuscator().transform_bytes,
                            None,
                            LMObfuscator().transform_bytes,
                            None,
                        ),
                    ),
                    construct.PascalString(construct.Int32ul, 'cp932'),
                )
            ),
            "offsets" / construct.Array(
                construct.this.count + 1,
                construct.Struct(
                    "offset_low" / construct.IfThenElse(
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
                    "offset_high" / construct.IfThenElse(
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
            "compress_types" / construct.Array(
                construct.this.count,
                construct.Enum(construct.Byte, LMCompressType)
            ),
            "unk1s" / construct.Array(
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
            "checksums" / construct.Array(
                construct.this.count,
                construct.Int32ul,
            ),
            "encrypt_flags" / construct.Array(
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
        return {'offset_low': offset & 0xffffffff, 'offset_high': (offset >> 32) << 31}

    @classmethod
    def directory_size(cls, version, filenames=[]):
        """Return the size of a directory containing `filenames`."""
        # we have to build an empty dir since construct sizeof() only works if
        # a struct has a fixed size
        count = len(filenames)
        directory = {
            'version': version,
            'count': count,
            'filenames': filenames,
            'offsets': [cls.split_offset(0)] * (count + 1),
            'compress_types': ['NONE'] * count,
            'unk1s': [0] * count,
            'checksums': [0] * count,
            'encrypt_flags': [0] * count,
        }
        return len(cls.struct().build(directory))

    @classmethod
    def checksum(cls, data):
        """Compute a VF archive checksum for the specified data.

        RE'd from TVrFile.ChecksumStream().

        Args:
            data (bytes): The data to checksum

        """
        csum = 0xffffffff
        for c in data:
            x = (csum & 0xff) ^ c
            x = VF_CHECKSUM_KEYS[x]
            csum = (csum >> 8) ^ x
        return csum ^ 0xffffffff


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

    def __init__(self, name=None, mode='r', fp=None, exe=None, version=DEFAULT_VERSION):
        self.closed = True
        if not name and fp:
            raise ValueError('Nothing to open')
        modes = {'r': 'rb', 'w': 'wb'}
        if mode not in modes:
            raise ValueError("mode must be 'r' or 'w'")
        self.mode = mode
        self._mode = modes[mode]

        if not fp:
            fp = open(name, self._mode)
            self._extfp = False
        else:
            if name is None and hasattr(fp, 'name') and isinstance(fp.name, (str, bytes)):
                name = fp.name
            if hasattr(fp, 'mode'):
                self._mode = fp.mode
            self._extfp = True
        self.fp = fp
        self.closed = False

        if name:
            self.name = str(Path(name).resolve())
        else:
            self.name = None

        self.filelist = []
        self.name_info = {}

        try:
            if mode == 'w':
                if exe:
                    self.exefp = open(exe, 'rb')
                    self.is_exe = True
                else:
                    self.is_exe = False
                    self.exefp = None
                self.tmpfp = tempfile.TemporaryFile()
                self.version = version
            else:
                self.exefp = None
                self.is_exe = False
                self.tmpfp = None
                savepos = self.fp.tell()
                self.archive_offset = self._find_archive_offset()
                self._parse_directory()
        except Exception as e:
            if self._extfp:
                self.fp.seek(savepos)
            else:
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
            if self.mode == 'w':
                self._write_exe()
                self._write_directory()
                self._write_archive()
                self._write_trailer()
        finally:
            if not self._extfp:
                self.fp.close()
            if self.exefp:
                self.exefp.close()
            if self.tmpfp:
                self.tmpfp.close()
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
            raise KeyError('{} does not exist in archive.'.format(name))
        return info

    def list(self):
        """Print a list of archive entries to stdout."""
        print(self.name)
        print('-------- ------ -------- -------- ------- ------')
        print(' Length   mode    unk1    chksum   flags   Name')
        print('-------- ------ -------- -------- ------- ------')
        for info in self.infolist():
            print('{:8} {:6} {:08x} {:08x} {:02x} {}'.format(
                info.compressed_size, info.compress_type.name, info.unk1, info.checksum, info.encrypt_flag, info.name))

    def _find_archive_offset(self):
        """Find offset for the start of the archive."""
        self.fp.seek(0)
        if self.fp.read(2) == b'MZ':
            # File is an MS executable
            self.is_exe = True
            self.fp.seek(-2, 2)
            # Check for 'lv' trailer
            if self.fp.read(2) != b'lv':
                raise BadLiveMakerArchive('EXE does not contain a LiveMaker archive.')
            # Read offset for start of archive
            self.fp.seek(-6, 2)
            offset, = struct.unpack('<I', self.fp.read(4))
            return offset
        else:
            self.is_exe = False
            return 0

    def _parse_directory(self):
        """Parse the file index for this archive."""
        self.fp.seek(self.archive_offset)
        directory = LMArchiveDirectory.struct().parse_stream(self.fp)
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
            raise ValueError('Archive is already closed.')
        if self.mode != 'r':
            raise ValueError('Cannot extract entry from archive which is open for writing.')
        if not isinstance(entry, LMArchiveInfo):
            entry = self.getinfo(entry)
        path = Path.joinpath(output_path, entry.path).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.read(entry)
        with path.open('wb') as f:
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
                log.warn('Skipping encrypted file {}'.format(e))

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
            raise ValueError('Archive is already closed.')
        if self.mode != 'r':
            raise ValueError('Cannot read entry in archive which is open for writing.')
        if isinstance(name, LMArchiveInfo):
            info = name
        else:
            info = self.getinfo(name)
        if decompress and info.compress_type not in SUPPORTED_COMPRESSIONS:
            raise UnsupportedLiveMakerCompression('{} is unsupported'.format(info.compress_type))
        self.fp.seek(self.archive_offset + info._offset)
        data = self.fp.read(info.compressed_size)
        if not skip_checksum and info.checksum is not None:
            if info.checksum != LMArchiveDirectory.checksum(data):
                log.warn('Bad checksum for file {}.'.format(info.name))
        if decompress:
            if info.compress_type == LMCompressType.ZLIB:
                data = zlib.decompress(data)
        return data

    def read_exe(self):
        """Return the exe bytes for this archive.

        Raises:
            ValueError: If this archive is not part of a LiveMaker executable
                (i.e. it is a ``.dat`` file).

        """
        if self.closed:
            raise ValueError('Archive is already closed.')
        if self.mode != 'r':
            raise ValueError('Cannot read exe from archive which is open for writing.')
        if not self.is_exe:
            raise ValueError('Archive is not part of a LiveMaker excecutable.')
        self.fp.seek(0)
        return self.fp.read(self.archive_offset)

    def write(self, filename, arcname=None, compress_type=None):
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
            raise ValueError('Archive is already closed.')
        if self.mode != 'w':
            raise ValueError('Cannot write to archive opened for reading.')
        if arcname is None:
            arcpath = PureWindowsPath(filename)
        else:
            arcpath = PureWindowsPath(arcname)
        # strip drive and leading pathsep
        name = str(arcpath.relative_to(arcpath.anchor))
        if name in self.name_info:
            raise FileExistsError('{} already exists in this archive.'.format(name))
        if compress_type is not None and compress_type not in SUPPORTED_COMPRESSIONS:
            raise UnsupportedLiveMakerCompression('{} is not supported.'.format(compress_type))
        info = LMArchiveInfo(name)
        with open(name, 'rb') as f:
            data = f.read()
        if compress_type is None:
            if len(data) >= 0x500000:
                compress_type = LMCompressType.ZLIB
            else:
                compress_type = LMCompressType.NONE
        if compress_type == LMCompressType.ZLIB:
            data = zlib.compress(data)
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
            raise ValueError('Archive is already closed.')
        if self.mode != 'w':
            raise ValueError('Cannot write to archive opened for reading.')
        if isinstance(arcname, LMArchiveInfo):
            info = LMArchiveInfo(arcname.name)
            info.compress_type = arcname.compress_type
            info.unk1 = arcname.unk1
            if skip_checksum:
                info.checksum = arcname.checksum
            info.encrypt_flag = arcname.encrypt_flag
        else:
            if compress_type is None:
                raise ValueError('Compression type must be specified')
            info = LMArchiveInfo(arcname)
            info.compress_type = compress_type
        if info.name in self.name_info:
            raise FileExistsError('{} already exists in this archive.'.format(arcname))
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
            'version': self.version,
            'count': len(self.filelist),
            'filenames': [],
            'offsets': [],
            'compress_types': [],
            'unk1s': [],
            'checksums': [],
            'encrypt_flags': [],
        }
        self.archive_offset = archive_offset = self.fp.tell()
        directory_size = LMArchiveDirectory.directory_size(self.version, self.name_info.keys())
        filenames = directory['filenames']
        offsets = directory['offsets']
        compress_types = directory['compress_types']
        unk1s = directory['unk1s']
        checksums = directory['checksums']
        encrypt_flags = directory['encrypt_flags']
        for info in self.filelist:
            filenames.append(info.name)
            # info offset will be the offset of this entry in the temporary
            # file (i.e. starting at 0). archive offsets need to start from the
            # end of the directory.
            offsets.append(LMArchiveDirectory.split_offset(info._offset + directory_size))
            compress_types.append(info.compress_type)
            unk1s.append(info.unk1)
            checksums.append(info.checksum)
            encrypt_flags.append(info.encrypt_flag)
        last_entry = self.filelist[-1]
        if last_entry is not None:
            offsets.append(LMArchiveDirectory.split_offset(
                last_entry._offset + directory_size + last_entry.compressed_size))
        else:
            offsets.append(LMArchiveDirectory.split_offset(archive_offset))
        data = LMArchiveDirectory.struct().build(directory)
        self.fp.write(data)

    def _write_archive(self):
        # copy data from temp file into final archive
        self.tmpfp.seek(0)
        shutil.copyfileobj(self.tmpfp, self.fp)

    def _write_trailer(self):
        data = struct.pack('<I', self.archive_offset)
        self.fp.write(data)
        self.fp.write(b'lv')


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

    def __init__(self, name=''):
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
