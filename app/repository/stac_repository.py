import json

from psycopg.types.json import Jsonb
from pystac import Item

from app.database import pool


def upsert(item: Item) -> bool:
    with pool.connection() as conn:
         return conn.execute(
            """
            INSERT INTO stac_items (
                collection,
                id,
                item,
                geometry,
                start_datetime,
                end_datetime,
                cloud_cover,
                processing_level
            ) VALUES (
                %(collection)s,
                %(id)s,
                %(item)s,
                ST_SetSRID(ST_GeomFromGeoJSON(%(geometry)s), 4326),
                %(start_datetime)s,
                %(end_datetime)s,
                %(cloud_cover)s,
                %(processing_level)s
            ) ON CONFLICT (collection, id)
             DO UPDATE SET item = EXCLUDED.item,
                           geometry = EXCLUDED.geometry,
                           start_datetime = EXCLUDED.start_datetime,
                           end_datetime = EXCLUDED.end_datetime,
                           cloud_cover = EXCLUDED.cloud_cover,
                           processing_level = EXCLUDED.processing_level,
                           updated_at = now()
             RETURNING (xmax = 0) AS inserted
            """,
            to_row(item),
        ).fetchone()[0]


def to_row(item: Item) -> dict:
    common = item.common_metadata
    return {
        "collection": item.collection_id,
        "id": item.id,
        "item": Jsonb(item.to_dict()),
        "geometry": json.dumps(item.geometry) if item.geometry else None,
        "start_datetime": common.start_datetime or item.datetime,
        "end_datetime": common.end_datetime or item.datetime,
        "cloud_cover": item.properties.get("eo:cloud_cover"),
        "processing_level": item.properties.get("processing:level"),
    }
