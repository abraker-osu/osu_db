import struct
import io

import logging


# from https://github.com/jaasonw/osu-db-tools/blob/master/buffer.py
class ReadBuffer:
    """
    Performs read operations on the osu! database

    Format nomenclature:
        Descriptions of format is provided as an array of types:
            [ <u32>, <f32>, <u8>, ... ]

        In <...> is the type of the value indicating raw
        encoding and size. Common types are:
            <u8>, <i8>, <u16>, <i16>, <u32>, <i32>, <u64>, <f32>, <f64>

        If there is an array of types, it is indicated by either `[len]`
        or `*`, depending on whether the length is predetermined. For example:
            [ <u32>, <f32*>, <u8[4]>, ... ]

        Following the type is `:fmt(name)` where `fmt` is optional and
        indicates the format in which the data is encoded, and `name`
        which is the name of the value. For example:
            [ <u8>, <u32:(len)>, <u16[len]:utf-16(str)> ]

        The format can consist of conditional parts. The `|` represents OR'ing
        of possible formats. For example, a byte that determines if the string
        is utf-8 or utf-16:
            [
                ( <u8:(0x00)>, <u32:(len)>, <u16[len]:utf-16(str)> ) |
                ( <u8:(0x01)>, <u32:(len)>, <u8[len]:utf-8(str)>   )
            ]

        The format is inspired by extended Backus-Naur form (EBNF) metasyntax.
            https://en.wikipedia.org/wiki/Extended_Backus%E2%80%93Naur_form
    """

    @staticmethod
    def read_bool(buffer: io.BufferedReader) -> bool:
        return struct.unpack('<?', buffer.read(1))[0]

    @staticmethod
    def read_ubyte(buffer: io.BufferedReader) -> int:
        return struct.unpack('<B', buffer.read(1))[0]

    @staticmethod
    def read_ushort(buffer: io.BufferedReader) -> int:
        return struct.unpack('<H', buffer.read(2))[0]

    @staticmethod
    def read_uint(buffer: io.BufferedReader) -> int:
        return struct.unpack('<I', buffer.read(4))[0]

    @staticmethod
    def read_float(buffer: io.BufferedReader) -> float:
        return struct.unpack('<f', buffer.read(4))[0]

    @staticmethod
    def read_double(buffer: io.BufferedReader) -> float:
        return struct.unpack('<d', buffer.read(8))[0]

    @staticmethod
    def read_ulong(buffer: io.BufferedReader) -> int:
        return struct.unpack('<Q', buffer.read(8))[0]


    @staticmethod
    def read_dynamic_value(buffer: io.BufferedReader) -> int | float:
        """
        Reads a (int | float | double) value

            Note: The osu! reference indicates that 0x0C and 0x0D are
            for distinct pairs of data, however it is obvious that the
            general purpose of such format is to provide a method of
            dynamically choosing a type of value. So given that 0x08
            resolves to an int, 0x0C to a float, and 0x0D to a double,
            this function has been generalized to apply such resolving
            to future proof against possible changes.

        Format:
            [
                ( <u8:(0x08)> <u32:(data)> ) |
                ( <u8:(0x0C)> <f32:(data)> ) |
                ( <u8:(0x0D)> <f64:(data)> )
            ]

        Reference:
            https://github.com/ppy/osu/wiki/Legacy-database-file-structure/da9169283d886241a9de121770435338800ece83#format

        Parameters
        ----------
        buffer : io.BufferedReader

        Returns
        -------
        (int, float, double)
            Value of the data
        """
        value_type = ReadBuffer.read_ubyte(buffer)
        match value_type:
            case 0x08: value = ReadBuffer.read_uint(buffer)
            case 0x0C: value = ReadBuffer.read_float(buffer)
            case 0x0D: value = ReadBuffer.read_double(buffer)
            case _:
                buffer.seek(-8, io.SEEK_CUR)
                raise ValueError(
                    f'Unexpected data type id: 0x{value_type:02x}\n'
                    'Rewinding back 8 bytes and reading next 16 bytes of data\n'
                    f'  last 8: {buffer.read(8).hex(" ")}  next 8: {buffer.read(8).hex(" ")}'
                )

        return value


    @staticmethod
    def read_string(buffer: io.BufferedReader) -> str:
        """
        Format:
            [ ( <u8:(0x00)> ) | ( <u8:(0x0B)> <u8*:uleb128(strlen)> <u8[strlen]:utf-8(str)> ) ]

        Reference:
            https://github.com/ppy/osu/wiki/Legacy-database-file-structure/da9169283d886241a9de121770435338800ece83#data-types
        """
        strlen, strflag = 0, ReadBuffer.read_ubyte(buffer)
        if strflag == 0x0b:
            strlen, shift = 0, 0

            # uleb128
            # https://en.wikipedia.org/wiki/LEB128
            while True:
                byte = ReadBuffer.read_ubyte(buffer)
                strlen |= ((byte & 0x7F) << shift)

                if (byte & (1 << 7)) == 0:
                    break

                shift += 7

        return (struct.unpack(f'<{strlen}s', buffer.read(strlen))[0]).decode('utf-8')


    @staticmethod
    def read_timing_point(buffer: io.BufferedReader):
        bpm       = ReadBuffer.read_double(buffer)
        offset    = ReadBuffer.read_double(buffer)
        inherited = ReadBuffer.read_bool(buffer)

        return (bpm, offset, inherited)


class WriteBuffer:

    def __init__(self):
        self.data = b''

    def write_bool(self, data: bool):    self.data += struct.pack('<?', data)
    def write_ubyte(self, data: int):    self.data += struct.pack('<B', data)
    def write_ushort(self, data: int):   self.data += struct.pack('<H', data)
    def write_uint(self, data: int):     self.data += struct.pack('<I', data)
    def write_float(self, data: float):  self.data += struct.pack('<f', data)
    def write_double(self, data: float): self.data += struct.pack('<d', data)
    def write_ulong(self, data: int):    self.data += struct.pack('<Q', data)

    def write_string(self, data: str):
        """
        Format:
            [ ( <u8:(0x00)> ) | ( <u8:(0x0B)> <u8*:uleb128(strlen)> <u8[strlen]:utf-8(str)> ) ]

        Reference:
            https://github.com/ppy/osu/wiki/Legacy-database-file-structure/da9169283d886241a9de121770435338800ece83#data-types
        """
        if len(data) <= 0:
            self.write_ubyte(0x0)
            return

        self.write_ubyte(0x0b)
        strlen = b''
        value = len(data)

        while value != 0:
            byte = (value & 0x7F)
            value >>= 7

            if (value != 0):
                byte |= 0x80

            strlen += struct.pack('<B', byte)

        self.data += strlen
        self.data += struct.pack(f'<{len(data)}s', data.encode('utf-8'))


    def clear_buffer(self):
        self.data = b''



# from https://github.com/jaasonw/osu-db-tools/blob/master/osu_to_sqlite.py
class OsuDbReader():

    __logger = logging.getLogger(__qualname__)

    @staticmethod
    def get_beatmap_md5_paths(filename: str):
        data = []

        with open(filename, 'rb') as db:
            version          = ReadBuffer.read_uint(db)
            folder_count     = ReadBuffer.read_uint(db)
            account_unlocked = ReadBuffer.read_bool(db)

            OsuDbReader.__logger.debug(f'osu!db version: {version}')

            # skip this datetime
            ReadBuffer.read_uint(db)
            ReadBuffer.read_uint(db)

            name             = ReadBuffer.read_string(db)
            num_beatmaps     = ReadBuffer.read_uint(db)

            for _ in range(num_beatmaps):
                artist             = ReadBuffer.read_string(db)
                artist_unicode     = ReadBuffer.read_string(db)
                song_title         = ReadBuffer.read_string(db)
                song_title_unicode = ReadBuffer.read_string(db)
                mapper             = ReadBuffer.read_string(db)
                difficulty         = ReadBuffer.read_string(db)
                audio_file         = ReadBuffer.read_string(db)
                md5_hash           = ReadBuffer.read_string(db)
                map_file           = ReadBuffer.read_string(db)
                ranked_status      = ReadBuffer.read_ubyte(db)
                num_hitcircles     = ReadBuffer.read_ushort(db)
                num_sliders        = ReadBuffer.read_ushort(db)
                num_spinners       = ReadBuffer.read_ushort(db)
                last_modified      = ReadBuffer.read_ulong(db)
                approach_rate      = ReadBuffer.read_float(db)
                circle_size        = ReadBuffer.read_float(db)
                hp_drain           = ReadBuffer.read_float(db)
                overall_difficulty = ReadBuffer.read_float(db)
                slider_velocity    = ReadBuffer.read_double(db)

                # An Int indicating the number of following Int-Float pairs, then the aforementioned pairs.
                # Star Rating info for each gamemode, in each pair, the Int is the mod combination, and the
                # Float is the Star Rating. Only present if version is >= 20140609.
                #
                # Reference: https://github.com/ppy/osu/wiki/Legacy-database-file-structure/da9169283d886241a9de121770435338800ece83#beatmap-information
                if version >= 20140609:
                    num_entries = ReadBuffer.read_uint(db)
                    for _ in range(num_entries):
                        std_mods = ReadBuffer.read_dynamic_value(db)
                        std_sr   = ReadBuffer.read_dynamic_value(db)

                    num_entries = ReadBuffer.read_uint(db)
                    for _ in range(num_entries):
                        taiko_mods = ReadBuffer.read_dynamic_value(db)
                        taiko_sr   = ReadBuffer.read_dynamic_value(db)

                    num_entries = ReadBuffer.read_uint(db)
                    for _ in range(num_entries):
                        catch_mods = ReadBuffer.read_dynamic_value(db)
                        catch_sr   = ReadBuffer.read_dynamic_value(db)

                    num_entries = ReadBuffer.read_uint(db)
                    for _ in range(num_entries):
                        mania_mods = ReadBuffer.read_dynamic_value(db)
                        mania_sr   = ReadBuffer.read_dynamic_value(db)

                drain_time   = ReadBuffer.read_uint(db)
                total_time   = ReadBuffer.read_uint(db)
                preview_time = ReadBuffer.read_uint(db)

                for _ in range(ReadBuffer.read_uint(db)):
                    ReadBuffer.read_timing_point(db)

                beatmap_id         = ReadBuffer.read_uint(db)
                beatmap_set_id     = ReadBuffer.read_uint(db)
                thread_id          = ReadBuffer.read_uint(db)
                grade_standard     = ReadBuffer.read_ubyte(db)
                grade_taiko        = ReadBuffer.read_ubyte(db)
                grade_ctb          = ReadBuffer.read_ubyte(db)
                grade_mania        = ReadBuffer.read_ubyte(db)
                local_offset       = ReadBuffer.read_ushort(db)
                stack_leniency     = ReadBuffer.read_float(db)
                gameplay_mode      = ReadBuffer.read_ubyte(db)
                song_source        = ReadBuffer.read_string(db)
                song_tags          = ReadBuffer.read_string(db)
                online_offset      = ReadBuffer.read_ushort(db)
                title_font         = ReadBuffer.read_string(db)
                is_unplayed        = ReadBuffer.read_bool(db)
                last_played        = ReadBuffer.read_ulong(db)
                is_osz2            = ReadBuffer.read_bool(db)
                folder_name        = ReadBuffer.read_string(db)
                last_checked       = ReadBuffer.read_ulong(db)
                ignore_sounds      = ReadBuffer.read_bool(db)
                ignore_skin        = ReadBuffer.read_bool(db)
                disable_storyboard = ReadBuffer.read_bool(db)
                disable_video      = ReadBuffer.read_bool(db)
                visual_override    = ReadBuffer.read_bool(db)
                last_modified2     = ReadBuffer.read_uint(db)
                scroll_speed       = ReadBuffer.read_ubyte(db)

                data.append({
                    'md5'  : md5_hash,
                    'path' : f'{folder_name.strip()}/{map_file.strip()}'
                })

        return data


    @staticmethod
    def get_num_beatmaps(filename: str):
        with open(filename, 'rb') as db:
            version          = ReadBuffer.read_uint(db)
            folder_count     = ReadBuffer.read_uint(db)
            account_unlocked = ReadBuffer.read_bool(db)

            # skip this datetime
            ReadBuffer.read_uint(db)
            ReadBuffer.read_uint(db)

            name         = ReadBuffer.read_string(db)
            num_beatmaps = ReadBuffer.read_uint(db)

        return num_beatmaps
