# -*- coding: utf-8
"""LiveMaker Gale (GAL/GaleX) image plugin for Python Imaging Library.

Copyright (C) 2019 Peter Rowlands <peter@pmrowla.com>
Copyright (C) 2014 tinfoil <https://bitbucket.org/tinfoil/>

This file is a part of pylivemaker.

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation, either version 3 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program. If not, see <http://www.gnu.org/licenses/>.
"""

import zlib
from binascii import unhexlify
from io import BytesIO

from lxml import etree

from PIL import Image, ImageFile, ImagePalette
from PIL._binary import i32le, si32le

from .exceptions import LiveMakerException


_GAL_MODE = {
    # TODO: support palette modes
    4: ("P", "P;4"),
    8: ("P", "P"),
    16: ("RGB", "BGR;15"),
    24: ("RGB", "BGR"),
    32: ("RGBA", "BGRA"),
}

_GAL_COMPRESSION = {
    0: "zip",
    2: "jpeg",
}


class GalImageError(IOError, LiveMakerException):
    pass


def _accept(prefix):
    return prefix[:4] == b"Gale"


class GalImageFile(ImageFile.ImageFile):
    """Image plugin for the LiveMaker GAL format."""

    format_description = "LiveMaker GAL"
    format = "GAL"

    def _galx_info(self, header):
        """LiveMaker GAL/X multiframe (multi-layer) image."""
        read = self.fp.read
        header += read(3)
        info = {}
        info["version"] = header[4:]
        if info["version"] == b"X200":
            header_size = i32le(read(4))
            xml = zlib.decompress(read(header_size))
            try:
                # Note: LiveMaker's code for generating GAL/X images sometimes
                # creates invalid XML, but setting recover=False should let
                # lxml deal with most of these cases.
                root = etree.fromstring(xml, parser=etree.XMLParser(encoding="shift-jis", recover=True))
            except etree.LxmlError as e:
                raise GalImageError("Could not parse GAL/X image XML metadata: {}".format(e))
            info["width"] = int(root.get("Width", 0))
            info["height"] = int(root.get("Height", 0))
            info["bpp"] = int(root.get("Bpp", 0))
            info["frame_count"] = int(root.get("Count", 0))
            info["compression"] = int(root.get("CompType", 0))
            info["compression_level"] = int(root.get("CompLevel", 0))
            info["randomized"] = root.get("Randomized") != "0"
            info["bg_color"] = int(root.get("BGColor", 0))
            info["block_width"] = int(root.get("BlockWidth", 0))
            info["block_height"] = int(root.get("BlockHeight", 0))
            info["offset"] = header_size + 12
            info["root"] = root
        else:
            raise GalImageError("Unsupported GAL/X version {}".format(header))
        if info["frame_count"] != len(root):
            print("Warning: frame count mismatch")
        info["frames"] = []
        for frame in root:
            frame_info = {}
            if len(frame) > 1:
                print("Warning: Frame contained multiple Layers tags")
            frame_info["name"] = frame.get("Name", "")
            # TODO: figure out what this bounding box is actually for
            # left = int(frame.get('L0', 0))
            # top = int(frame.get('T0', 0))
            # right = int(frame.get('R0', info['width']))
            # bottom = int(frame.get('B0', info['height']))
            # frame_info['box'] = (left, top, right, bottom)
            frame_info["box"] = (0, 0, info["width"], info["height"])
            for layers in frame:
                frame_info["width"] = int(layers.get("Width", info["width"]))
                frame_info["height"] = int(layers.get("Height", info["height"]))
                frame_info["bpp"] = int(layers.get("bpp", info["bpp"]))
                stride = (frame_info["width"] * frame_info["bpp"] + 7) // 8
                if frame_info["bpp"] >= 8:
                    # align to 4 byte boundary
                    stride = (stride + 3) & ~3
                if frame_info["bpp"] <= 8:
                    for rgb in layers.iter("RGB"):
                        palette = unhexlify(rgb.text)
                        frame_info["palette"] = ImagePalette.raw("BGR", palette)
                else:
                    frame_info["palette"] = None
                frame_info["stride"] = stride
                frame_info["alpha_stride"] = (frame_info["width"] + 3) & ~3
                frame_info["layers"] = []
                for layer in layers.iter("Layer"):
                    layer_info = {}
                    left = int(layer.get("Left", 0))
                    top = int(layer.get("Top", 0))
                    layer_info["origin"] = (left, top)
                    layer_info["trans_color"] = int(layer.get("TransColor", -1))
                    layer_info["visible"] = int(layer.get("Visible", 1))
                    layer_info["alpha"] = int(layer.get("Alpha", 255))
                    layer_info["alpha_on"] = int(layer.get("AlphaOn", 0))
                    frame_info["layers"].append(layer_info)
            info["frames"].append(frame_info)
        return info

    def _galx_frames(self, info):
        frames = []
        offsets = []
        self.fp.seek(info["offset"])
        for frame in info["frames"]:
            if info["bpp"] not in _GAL_MODE:
                raise GalImageError("Unsupported GAL pixel format")
            mode, rawmode = _GAL_MODE[frame["bpp"]]
            layermode = mode
            if len(frame["layers"]) > 1:
                print("Warning multi-layer GAL/X image")
            for layer in frame["layers"]:
                offsets.append(self.fp.tell())
                layer_size = si32le(self.fp.read(4))
                self.fp.seek(layer_size, 1)
                if layer["alpha_on"]:
                    alpha_size = si32le(self.fp.read(4))
                    self.fp.seek(alpha_size, 1)
                    if mode == "RGB":
                        mode = "RGBA"
                    elif mode == "P":
                        mode = "PA"
                    else:
                        raise GalImageError("unsupported GAL alpha mode")
                    break
                break
            frames.append(
                (frame["name"], len(frame["layers"]), mode, layermode, rawmode, frame["box"], frame["palette"])
            )
        return frames, offsets

    def _gal_info(self, header):
        """LiveMaker GAL image."""
        read, seek = self.fp.read, self.fp.seek
        header += read(2)
        info = {}
        info["version"] = header[4:]
        try:
            version = int(info["version"])
        except ValueError:
            raise GalImageError("Unsupported GAL version {}".format(header))
        if version > 102:
            header_size = si32le(read(4))
            header = read(header_size)
            info["width"] = i32le(header, 4)
            info["height"] = i32le(header, 8)
            info["bpp"] = si32le(header, 0xC)
            info["frame_count"] = si32le(header, 0x10)
            if info["frame_count"] > 1:
                print("Warning: multi-frame GAL images are not fully supported")
            info["randomized"] = header[0x15]
            info["compression"] = header[0x16]
            info["bg_color"] = i32le(header, 0x18)
            info["block_width"] = si32le(header, 0x1C)
            info["block_height"] = si32le(header, 0x20)
            info["offset"] = header_size + 11
        elif version >= 100:
            # fixed header size
            header = read(0x10)
            name_length = i32le(header)
            seek(name_length + 17, 1)
            info["width"] = i32le(header, 4)
            info["height"] = i32le(header, 8)
            info["bpp"] = si32le(header, 0xC)
            info["offset"] = name_length + 45
            info["block_width"] = 0
            info["block_height"] = 0
            info["randomized"] = 0
            info["compression"] = None
            info["frame_count"] = 1
        else:
            raise GalImageError("Unsupported GAL version {}".format(header))
        return info

    def _gal_frames(self, info):
        read = self.fp.read
        seek = self.fp.seek
        frames = []
        offsets = []
        seek(info["offset"])
        info["frames"] = []
        for i in range(info["frame_count"]):
            frame_info = {}
            name_len = i32le(read(4))
            frame_info["name"] = read(name_len).decode("cp932")
            mask = i32le(read(4))
            seek(9, 1)
            layer_count = i32le(read(4))
            if layer_count < 1:
                raise GalImageError("Invalid GAL frame")
            frame_info["width"] = si32le(read(4))
            frame_info["height"] = si32le(read(4))
            bpp = i32le(read(4))
            if bpp not in _GAL_MODE or bpp > 32:
                print(layer_count)
                print(frame_info, mask)
                print(bpp)
                raise GalImageError("Unsupported GAL pixel format")
            frame_info["bpp"] = bpp
            if bpp <= 8:
                palette_size = 1 << bpp
                frame_info["palette"] = ImagePalette.raw("BGRX", read(palette_size * 4))
            else:
                frame_info["palette"] = None
            mode, rawmode = _GAL_MODE[bpp]
            layermode = mode
            stride = (frame_info["width"] * bpp + 7) // 8
            if bpp >= 8:
                # align to 4 byte boundary
                stride = (stride + 3) & ~3
            frame_info["stride"] = stride
            frame_info["alpha_stride"] = (frame_info["width"] + 3) & ~3
            frame_info["layers"] = []
            for j in range(layer_count):
                layer_info = {}
                left = si32le(read(4))
                top = si32le(read(4))
                layer_info["origin"] = (left, top)
                layer_info["visible"] = read(1)[0]
                layer_info["trans_color"] = si32le(read(4))
                layer_info["alpha"] = si32le(read(4))
                layer_info["alpha_on"] = read(1)[0]
                name_len = i32le(read(4))
                seek(name_len, 1)
                if int(info["version"]) >= 107:
                    layer_info["lock"] = read(1)[0]
                if j == 0:
                    offsets.append(self.fp.tell())
                else:
                    print("Warning: multilayer Gale images not fully supported")
                layer_size = si32le(read(4))
                seek(layer_size, 1)
                alpha_size = si32le(read(4))
                if layer_info["alpha_on"] and alpha_size > 0:
                    if mode == "RGB":
                        mode = "RGBA"
                    elif mode == "P":
                        mode = "PA"
                    else:
                        raise GalImageError("unsupported GAL alpha mode")
                seek(alpha_size, 1)
                frame_info["layers"].append(layer_info)
            info["frames"].append(frame_info)
            box = (0, 0, frame_info["width"], frame_info["height"])
            frames.append((frame_info["name"], layer_count, mode, layermode, rawmode, box, frame_info["palette"]))
            # TODO: handle multi-frame images
            break
        return frames, offsets

    def _open(self):
        header = self.fp.read(5)
        if header == b"GaleX":
            info = self._galx_info(header)
            frames, offsets = self._galx_frames(info)
        else:
            info = self._gal_info(header)
            frames, offsets = self._gal_frames(info)
        self._size = info["width"], info["height"]
        self.decoder = "GAL"
        if info["randomized"]:
            raise GalImageError("LiveMaker Pro encrypted images are currently unsupported")

        i = 0
        for name, layer_count, mode, layermode, rawmode, box, palette in frames:
            tile = None
            offset = offsets[i]
            tile = [(self.decoder, box, offset, (info, layermode, rawmode, i))]
            frames[i] = name, mode, box, palette, tile
        self.fp.seek(info["offset"])
        self.frames = frames
        self._frame = None
        self.seek(0)

    @property
    def is_animated(self):
        return len(self.frames) > 1

    @property
    def n_frames(self):
        return len(self.frames)

    def seek(self, frame):
        if not self._seek_check(frame):
            return

        try:
            name, mode, box, palette, tile = self.frames[frame]
            self.mode = mode
            self.tile = tile
            self.palette = palette
            self._frame = frame
        except IndexError:
            raise EOFError("Invalid GAL frame")

    def tell(self):
        return self._frame


class GalImageDecoder(ImageFile.PyDecoder):

    _pulls_fd = True

    def decode(self, buffer):
        info, layermode, rawmode, frame_index = self.args
        compression = _GAL_COMPRESSION.get(info["compression"])
        frame = info["frames"][frame_index]
        for layer in frame["layers"]:
            layer_size = si32le(self.fd.read(4))
            if compression == "zip":
                packed_data = zlib.decompress(self.fd.read(layer_size))
                layer["data"] = self._unpack_layer(
                    BytesIO(packed_data),
                    frame,
                    info["block_width"],
                    info["block_height"],
                    info["randomized"],
                    info["frames"],
                )
                self._set_as_raw(layer["data"], layermode, rawmode, frame["stride"])
                if layer["alpha_on"]:
                    self._decode_alpha(frame, info)
            elif compression == "jpeg":
                jpeg_data = self.fd.read(layer_size)
                self._set_as_jpeg(jpeg_data, layermode)
                if layer["alpha_on"]:
                    self._decode_alpha(frame, info)
            else:
                packed_data = self.fd.read(layer_size)
                layer["data"] = self._unpack_layer(
                    BytesIO(packed_data),
                    frame,
                    info["block_width"],
                    info["block_height"],
                    info["randomized"],
                    info["frames"],
                )
                self._set_as_raw(layer["data"], layermode, rawmode, frame["stride"])
            # TODO: handle multi-layer frames
            break
        return 0, 0

    def _decode_alpha(self, frame, info):
        alpha_size = si32le(self.fd.read(4))
        packed_data = zlib.decompress(self.fd.read(alpha_size))
        unpacked = self._unpack_layer(
            BytesIO(packed_data),
            frame,
            info["block_width"],
            info["block_height"],
            info["randomized"],
            info["frames"],
            True,
        )
        size = self.state.xsize, self.state.ysize
        mask = Image.frombytes("L", size, unpacked, "raw", "L", frame["alpha_stride"])
        if Image.getmodebase(self.mode) == "RGB":
            band = 3
        else:
            band = 1
        self.im.putband(mask.im, band)

    def _unpack_layer(self, packed, frame_info, block_width, block_height, randomized, frames, is_alpha=False):
        # Based on GARbro ImageGAL.cs:ReadBlocks() implementation
        if block_width <= 0 or block_height <= 0:
            return packed.read()
        width = frame_info["width"]
        height = frame_info["height"]
        if is_alpha:
            bpp = 8
            stride = frame_info["alpha_stride"]
        else:
            bpp = frame_info["bpp"]
            stride = frame_info["stride"]
        blocks_w = (width + block_width - 1) // block_width
        blocks_h = (height + block_height - 1) // block_height
        blocks_count = blocks_w * blocks_h
        block_refs = []
        for i in range(blocks_count):
            frame_ref = si32le(packed.read(4))
            layer_ref = si32le(packed.read(4))
            block_refs.append((frame_ref, layer_ref))
        if randomized:
            raise GalImageError("LivemakerPro encrypted images are unsupported")
        i = 0
        data = bytearray(stride * height)
        for y in range(0, height, block_height):
            # account for block size alignment padding
            run_height = min(block_height, height - y)
            for x in range(0, width, block_width):
                frame_ref, layer_ref = block_refs[i]

                run_width = min(block_width, width - x)
                dst = y * stride + (x * bpp + 7) // 8
                chunk_size = (run_width * bpp + 7) // 8
                if frame_ref == -1:
                    # read block as raw data
                    for j in range(run_height):
                        chunk = packed.read(chunk_size)
                        for k in range(chunk_size):
                            data[dst + k] = chunk[k]
                        dst += stride
                elif frame_ref == -2:
                    # copy block from this layer
                    src_x = block_width * (layer_ref % blocks_w)
                    src_y = block_height * (layer_ref // blocks_w)
                    src = src_y * stride + (src_x * bpp + 7) // 8
                    for j in range(run_height):
                        for k in range(chunk_size):
                            data[dst + k] = data[src + k]
                        src += stride
                        dst += stride
                else:
                    # copy block from another frame/layer
                    if frame_ref >= len(frames) or layer_ref >= len(frames[frame_ref]["layers"]):
                        raise GalImageError("Invalid GaleFrame reference")
                    if is_alpha:
                        ref_data = frames[frame_ref]["layers"][layer_ref]["alpha_data"]
                    else:
                        ref_data = frames[frame_ref]["layers"][layer_ref]["data"]
                    for j in range(run_height):
                        for k in range(chunk_size):
                            data[dst + k] = ref_data[dst + k]
                i += 1
        return bytes(data)

    def _set_as_raw(self, data, mode, rawmode=None, stride=0):
        # override PIL set_as_raw() so we can set stride
        if not rawmode:
            rawmode = mode
        d = Image._getdecoder(mode, "raw", (rawmode, stride, 1))
        d.setimage(self.im, self.state.extents())
        s = d.decode(data)

        if s[0] >= 0:
            raise GalImageError("not enough image data")
        if s[1] != 0:
            raise GalImageError("cannot decode image data")

    def _set_as_jpeg(self, data, mode):
        from PIL.JpegImagePlugin import RAWMODE

        d = Image._getdecoder(mode, "jpeg", (RAWMODE[mode], ""))
        d.setimage(self.im, self.state.extents())
        s = d.decode(data)

        if s[0] >= 0:
            raise GalImageError("not enough image data")
        if s[1] != 0:
            raise GalImageError("cannot decode image data")


Image.register_decoder("GAL", GalImageDecoder)

Image.register_open(GalImageFile.format, GalImageFile, _accept)
Image.register_extensions(GalImageFile.format, [".gal"])
