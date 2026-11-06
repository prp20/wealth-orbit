"""Resolve a market_data.data_sources row without colliding on source_name."""
from __future__ import annotations

import uuid


def ensure_data_source(cur, name: str) -> uuid.UUID:
    """Return the source_id for name, creating the row when it is absent.

    NAV and enrichment jobs both insert ``mftool``. A select followed by an
    insert loses that race and raises data_sources_source_name_key. ON CONFLICT
    waits for the other insert, then the select reads the committed row.
    """
    cur.execute(
        """INSERT INTO market_data.data_sources (source_id, source_name)
           VALUES (%s, %s)
           ON CONFLICT (source_name) DO NOTHING
           RETURNING source_id""",
        (str(uuid.uuid4()), name),
    )
    created = cur.fetchone()
    if created:
        return created[0]
    cur.execute(
        "SELECT source_id FROM market_data.data_sources WHERE source_name=%s",
        (name,),
    )
    found = cur.fetchone()
    if not found:
        raise RuntimeError(f"Unable to resolve data source {name}")
    return found[0]
