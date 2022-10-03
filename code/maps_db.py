import sqlite3
import logging
import threading
import os

from .osu_db_reader import OsuDbReader


# For resolving replays to maps
class MapsDB():

    def __init__(self, osu_path):
        self.__stream_handler = logging.StreamHandler()
        self.__stream_handler.setFormatter(logging.Formatter('%(levelname)s %(asctime)s  [ %(name)s ] %(message)s'))

        self.__logger = logging.getLogger(self.__class__.__name__)
        self.__logger.addHandler(self.__stream_handler)

        # Create the maps.db file containing a list of map paths and their md5 hash
        os.makedirs('data', exist_ok=True)
        self.__db = sqlite3.connect('data/maps.db', check_same_thread=False)
        self.__osu_path = osu_path
        self.__osu_db_path = f'{osu_path}/osu!.db'

        # This is required because it is possible to read
        # MapDB data from another thread but not write to it
        self.__thread_id = threading.get_ident()

        if not os.path.exists(self.__osu_path):
            self.__osu_path = None
            raise FileNotFoundError(f'"{self.__osu_path}" does not exist!')

        if not os.path.isfile(self.__osu_db_path):
            self.__osu_db_path = None
            raise FileNotFoundError(f'"{self.__osu_db_path}" does not exist!')

        self.check_db()


    def __check_maps_table(self):
        self.__logger.debug('Checking maps table')

        # Check if if the "maps" table exists
        reply = self.__db.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='maps'").fetchone()[0]
        if reply > 0:
            self.__logger.debug('Map table ok')
            return False

        self.__logger.info('Map table does not exist - creating')
        self.__db.execute("CREATE TABLE maps(md5 TEXT, path TEXT)")

        columns = ', '.join([ 'md5', 'path' ])
        placeholders = ':' + ', :'.join([ 'md5', 'path' ])

        data = OsuDbReader.get_beatmap_md5_paths(self.__osu_db_path)
        for entry in data:
            self.__db.execute(f'INSERT INTO maps ({columns}) VALUES ({placeholders});', tuple(entry[k] for k in entry.keys()))
        self.__db.commit()

        self.__logger.debug('Map table created')
        return True


    def __check_meta_table(self):
        self.__logger.debug('Checking meta table')

        # Check if the "meta" table exists
        reply = self.__db.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='meta'").fetchone()[0]
        if reply > 0:
            self.__logger.debug('Meta table ok')
            return False

        self.__logger.info('Meta table does not exist - creating')
        self.__db.execute("CREATE TABLE meta(num_maps INT, last_modified REAL)")

        num_beatmaps_read = OsuDbReader.get_num_beatmaps(self.__osu_db_path)
        last_modified_read = os.stat(self.__osu_db_path).st_mtime

        columns = ', '.join([ 'num_maps', 'last_modified' ])
        placeholders = ':' + ', :'.join([ 'num_maps', 'last_modified' ])

        self.__db.execute(f'INSERT INTO meta ({columns}) VALUES ({placeholders});', (num_beatmaps_read, last_modified_read))
        self.__db.commit()

        self.__logger.debug('Meta table created')
        return True


    def check_db(self):
        maps_table_built = self.__check_maps_table()
        meta_table_built = self.__check_meta_table()

        if maps_table_built and meta_table_built:
            num_beatmaps_save = self.__db.execute('SELECT num_maps FROM meta').fetchone()
            if num_beatmaps_save is not None:
                self.__logger.info(f'db containing {num_beatmaps_save[0]} maps loaded')
            else:
                self.__logger.warning('Unable to read meta table!')
            return
        
        num_beatmaps_read = OsuDbReader.get_num_beatmaps(self.__osu_db_path)
        num_beatmaps_save = self.__db.execute('SELECT num_maps FROM meta').fetchone()
        if num_beatmaps_save is not None:
            num_beatmaps_save = num_beatmaps_save[0]

        last_modified_read = os.stat(self.__osu_db_path).st_mtime
        last_modified_save = self.__db.execute('SELECT last_modified FROM meta').fetchone()
        if last_modified_save is not None:
            last_modified_save = last_modified_save[0]

        num_maps_changed = num_beatmaps_read != num_beatmaps_save
        osu_db_modified = last_modified_read != last_modified_save

        if num_maps_changed or osu_db_modified:
            if osu_db_modified:
                self.__logger.info(f'osu!.db was modified. If you modified or added maps, they will not be found until you update db')
                return

            self.__update_maps_db()

            if num_beatmaps_save is not None:
                self.__logger.info(f'Added {num_beatmaps_read - num_beatmaps_save} new maps')
            else:
                self.__logger.info(f'Added {num_beatmaps_read} new maps')
            return


    def __update_maps_db(self):
        thread_id = threading.get_ident()
        if thread_id != self.__thread_id:
            raise threading.ThreadError('Attempt to write to MapsDB from another thread')

        num_beatmaps_read = OsuDbReader.get_num_beatmaps(self.__osu_db_path)
        last_modified_read = os.stat(self.__osu_db_path).st_mtime

        data = OsuDbReader.get_beatmap_md5_paths(f'{MapsDB.osu_path}/osu!.db')

        # Insert missing entries
        columns = ', '.join([ 'md5', 'path' ])
        placeholders = ':' + ', :'.join([ 'md5', 'path' ])
        
        # Drop "maps" table
        self.__db.execute('DROP TABLE maps')
        self.__db.commit()

        self.__db.execute("CREATE TABLE meta(num_maps INT, last_modified REAL)")

        # Add map entries into table
        for entry in data:
            self.__db.execute(f'INSERT INTO maps ({columns}) VALUES ({placeholders});', tuple(entry[k] for k in entry.keys()))

        self.__db.execute(f'UPDATE meta SET num_maps = {num_beatmaps_read};')
        self.__db.execute(f'UPDATE meta SET last_modified = {last_modified_read};')

        self.__db.commit()


    def get_map_file_name(self, map_md5, filename=True):
        reply = self.__db.execute(f'SELECT path FROM maps WHERE md5 = "{map_md5}"').fetchone()
        if reply is not None:
            map_file_name = f'{self.__osu_path}/Songs/{reply[0]}' if filename else reply[0]
            return map_file_name

        return None
