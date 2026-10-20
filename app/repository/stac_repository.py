import json

from psycopg.types.json import Jsonb
from pystac import Item

from app.database import pool
from app.model.search import SearchRequest

UPSERT_ITEM_SQL = """
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
        ST_GeomFromGeoJSON(%(geometry)s),
        %(start_datetime)s,
        %(end_datetime)s,
        %(cloud_cover)s,
        %(processing_level)s
    ) ON CONFLICT (collection, id)
    DO UPDATE SET
        item = EXCLUDED.item,
        geometry = EXCLUDED.geometry,
        start_datetime = EXCLUDED.start_datetime,
        end_datetime = EXCLUDED.end_datetime,
        cloud_cover = EXCLUDED.cloud_cover,
        processing_level = EXCLUDED.processing_level,
        updated_at = now()
    RETURNING (old.id IS NULL) AS inserted
"""


def upsert(item: Item) -> bool:
    with pool.connection() as conn:
        return conn.execute(UPSERT_ITEM_SQL, _to_row(item)).fetchone()[0]


def _to_row(item: Item) -> dict:
    common = item.common_metadata
    return {
        "collection": item.collection_id,
        "id": item.id,
        "item": Jsonb(item.to_dict()),
        "geometry": json.dumps(item.geometry),
        "start_datetime": common.start_datetime or item.datetime,
        "end_datetime": common.end_datetime or item.datetime,
        "cloud_cover": item.properties.get("eo:cloud_cover"),
        "processing_level": item.properties.get("processing:level"),
    }


def find_items(search_request: SearchRequest) -> list[Item]:
    conditions = []
    params = []

    if search_request.bbox is not None:
        conditions.append(
            "ST_Intersects(geometry, ST_MakeEnvelope(%s, %s, %s, %s, 4326))"
        )
        params.extend(search_request.bbox)

    if search_request.start_datetime is not None:
        conditions.append("end_datetime >= %s")
        params.append(search_request.start_datetime)

    if search_request.end_datetime is not None:
        conditions.append("start_datetime <= %s")
        params.append(search_request.end_datetime)

    if search_request.max_cloud_coverage is not None:
        conditions.append("cloud_cover <= %s")
        params.append(search_request.max_cloud_coverage)

    if search_request.processing_level is not None:
        conditions.append("processing_level = %s")
        params.append(search_request.processing_level)

    params.extend([search_request.limit, search_request.offset])

    where = f" WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT item FROM stac_items{where} ORDER BY start_datetime DESC, collection, id LIMIT %s OFFSET %s"
    with pool.connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [Item.from_dict(row[0]) for row in rows]
