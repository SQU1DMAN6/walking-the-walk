import struct
import zlib
from pathlib import Path


def save_png(path, width, height, rgb):
    stride = width*3
    data = bytes(rgb)
    rows = b''.join(b'\0'+data[y*stride:(y+1)*stride] for y in range(height-1, -1, -1))

    def chunk(kind, payload):
        return struct.pack('!I', len(payload))+kind+payload+struct.pack('!I', zlib.crc32(kind+payload))

    png = (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!2I5B', width, height, 8, 2, 0, 0, 0))
           + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b''))
    Path(path).write_bytes(png)
