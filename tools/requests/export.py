#!/usr/bin/env python3
"""Read-only dated export of the two vehicle request collections."""

from __future__ import annotations

import base64
import os
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

from google.cloud import firestore
from google.cloud.firestore_v1.services.firestore import FirestoreClient
from google.cloud.firestore_v1 import _helpers
import google.auth


PROJECT = "open-road-60dbc"
COLLECTIONS = ("vehicleModelRequests", "vehicleModelRequestsAgg")
ROOT = Path(os.environ["REQUESTS_DELTA"])
DATA_DIR = ROOT / "data"
RUN_DATE = os.environ["REQUESTS_DATE"]


def jsonable(value: Any) -> Any:
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return {"__type__": "bytes", "base64": base64.b64encode(value).decode("ascii")}
    if isinstance(value, firestore.DocumentReference):
        return {"__type__": "document_reference", "path": value.path}
    if isinstance(value, firestore.GeoPoint):
        return {"__type__": "geopoint", "latitude": value.latitude, "longitude": value.longitude}
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value


def export_collection(client: firestore.Client, collection: str) -> tuple[Path, int, str]:
    # A single collection get. Do not mutate or acknowledge any document.
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/datastore'])
    service = FirestoreClient(credentials=credentials, transport='rest')
    snapshots = service.list_documents(request={
        'parent': f'projects/{PROJECT}/databases/(default)/documents',
        'collection_id': collection, 'page_size': 1000,
    }, timeout=90, retry=None)
    documents = []
    for snapshot in snapshots:
        documents.append(
            {
                "id": snapshot.name.rsplit("/", 1)[-1],
                "createTime": jsonable(snapshot.create_time),
                "updateTime": jsonable(snapshot.update_time),
                "data": jsonable(_helpers.decode_dict(snapshot.fields, client)),
            }
        )

    payload = {
        "project": PROJECT,
        "collection": collection,
        "readAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "documentCount": len(documents),
        "documents": documents,
    }
    output = DATA_DIR / f"{collection}-raw-{RUN_DATE}.json"
    output.touch(mode=0o600, exist_ok=True)
    output.chmod(0o600)
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return output, len(documents), digest


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = firestore.Client(project=PROJECT)
    for collection in COLLECTIONS:
        output, count, digest = export_collection(client, collection)
        print(f"collection={collection} docs={count} bytes={output.stat().st_size} sha256={digest}")


if __name__ == "__main__":
    main()
