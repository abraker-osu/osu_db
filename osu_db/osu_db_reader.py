import struct


# from https://github.com/jaasonw/osu-db-tools/blob/master/buffer.py
class ReadBuffer:

    @staticmethod
    def read_bool(buffer) -> bool:
        return struct.unpack('<?', buffer.read(1))[0]

    @staticmethod
    def read_ubyte(buffer) -> int:
        return struct.unpack('<B', buffer.read(1))[0]

    @staticmethod
    def read_ushort(buffer) -> int:
        return struct.unpack('<H', buffer.read(2))[0]

    @staticmethod
    def read_uint(buffer) -> int:
        return struct.unpack('<I', buffer.read(4))[0]

    @staticmethod
    def read_float(buffer) -> float:
        return struct.unpack('<f', buffer.read(4))[0]

    @staticmethod
    def read_double(buffer) -> float:
        return struct.unpack('<d', buffer.read(8))[0]


    @staticmethod
    def read_ulong(buffer) -> int:
        return struct.unpack('<Q', buffer.read(8))[0]


    # osu specific
    @staticmethod
    def read_int_double(buffer):
        ReadBuffer.read_ubyte(buffer)
        integer = ReadBuffer.read_uint(buffer)
        ReadBuffer.read_ubyte(buffer)
        double = ReadBuffer.read_double(buffer)
        return (integer, double)


    @staticmethod
    def read_timing_point(buffer):
        bpm       = ReadBuffer.read_double(buffer)
        offset    = ReadBuffer.read_double(buffer)
        inherited = ReadBuffer.read_bool(buffer)
        return (bpm, offset, inherited)


    @staticmethod
    def read_string(buffer) -> str:
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

    @staticmethod
    def get_beatmap_md5_paths(filename):
        data = []

        with open(filename, 'rb') as db:
            version          = ReadBuffer.read_uint(db)
            folder_count     = ReadBuffer.read_uint(db)
            account_unlocked = ReadBuffer.read_bool(db)
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
                
                i = ReadBuffer.read_uint(db)
                for _ in range(i):
                    ReadBuffer.read_int_double(db)

                i = ReadBuffer.read_uint(db)
                for _ in range(i):
                    ReadBuffer.read_int_double(db)

                i = ReadBuffer.read_uint(db)
                for _ in range(i):
                    ReadBuffer.read_int_double(db)

                i = ReadBuffer.read_uint(db)
                for _ in range(i):
                    ReadBuffer.read_int_double(db)

                drain_time   = ReadBuffer.read_uint(db)
                total_time   = ReadBuffer.read_uint(db)
                preview_time = ReadBuffer.read_uint(db)

                # skip timing points
                # i = ReadBuffer.read_uint(db)

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
    def get_num_beatmaps(filename):
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
