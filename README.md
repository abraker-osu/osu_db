# osu_db

### About

A helper library for reading the osu!.db and build a list of md5 <-> beatmap path relations. It creates a sqlite data base as ./data/maps.db which contains the following tables:

```
TABLE maps(md5 TEXT, path TEXT)
TABLE meta(num_maps INT, last_modified REAL)
```

This is mainly used for determining where to find a beatmap for a given replay, in conjunction with [osu_recorder](https://github.com/orgs/abraker-osu/repositories).
Do note osu!.db gets updated only when osu! closes, so any new beatmaps added while osu! is open will not be found.

# Use
To start using just create a new `MapsDB` object, giving it the osu! path:
```py
maps_db = MapsDB('K:/Games/osu!')
```

On first run it may take a few seconds for it to parse through osu!.db and build the tables.
To resolve beatmaps:

```py
map_path = maps_db.get_map_file_name(map_md5, filepath=True)
```
When `filepath` is true, it will return the full path to the beatmap, otherwise it will return the name of the beatmap file

To refresh the db with new maps:
```py
maps_db.check_db()
```

And that's pretty much all there is to it
