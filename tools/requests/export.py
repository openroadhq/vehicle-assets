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


STORE = Path(os.environ.get("REQUESTS_STORE", Path.home() / "Projects/vehicle-request-state/store"))
# Field that moves forward whenever a document matters to us: requests are create-only; the
# aggregate is bumped on every new request for that slug.
WATERMARK_FIELD = {"vehicleModelRequests": "createdAt", "vehicleModelRequestsAgg": "lastRequestedAt"}
FULL_EVERY = dt.timedelta(hours=24)
OVERLAP = dt.timedelta(minutes=30)


def write_payload(collection: str, documents: list[dict[str, Any]]) -> tuple[Path, int, str]:
    documents = sorted(documents, key=lambda d: d["id"])
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
    return output, len(documents), hashlib.sha256(output.read_bytes()).hexdigest()


def incremental(client: firestore.Client, collection: str) -> tuple[Path, int, str, int] | None:
    """Read only documents changed since the last run, merged into a local store. None means do a full read."""
    store = STORE / f"{collection}.json"
    if not store.exists():
        return None
    saved = json.loads(store.read_text())
    full_at = dt.datetime.fromisoformat(saved["fullReadAt"])
    if dt.datetime.now(dt.timezone.utc) - full_at > FULL_EVERY:
        return None
    field = WATERMARK_FIELD[collection]
    since = dt.datetime.fromisoformat(saved["watermark"]) - OVERLAP
    from google.cloud.firestore_v1.base_query import FieldFilter
    docs = {d["id"]: d for d in saved["documents"]}
    fetched = 0
    for snap in client.collection(collection).where(filter=FieldFilter(field, ">", since)).stream(timeout=90):
        fetched += 1
        docs[snap.id] = {"id": snap.id, "createTime": jsonable(snap.create_time),
                         "updateTime": jsonable(snap.update_time), "data": jsonable(snap.to_dict())}
    save_store(collection, list(docs.values()), saved["fullReadAt"])
    return (*write_payload(collection, list(docs.values())), fetched)


def save_store(collection: str, documents: list[dict[str, Any]], full_read_at: str) -> None:
    field = WATERMARK_FIELD[collection]
    stamps = [d["data"].get(field) for d in documents if isinstance(d["data"].get(field), str)]
    STORE.mkdir(parents=True, exist_ok=True)
    tmp = STORE / f"{collection}.json.tmp"
    tmp.write_text(json.dumps({"fullReadAt": full_read_at, "watermark": max(stamps) if stamps else full_read_at,
                               "documents": documents}) + "\n")
    tmp.replace(STORE / f"{collection}.json")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = firestore.Client(project=PROJECT)
    for collection in COLLECTIONS:
        result = None
        try:
            result = incremental(client, collection)
        except Exception as exc:
            print(f"collection={collection} incremental read failed ({type(exc).__name__}); doing a full read")
        if result:
            output, count, digest, fetched = result
            print(f"collection={collection} docs={count} fetched={fetched} (incremental) sha256={digest}")
            continue
        read_at = dt.datetime.now(dt.timezone.utc).isoformat()
        output, count, digest = export_collection(client, collection)
        save_store(collection, json.loads(output.read_text())["documents"], read_at)
        print(f"collection={collection} docs={count} bytes={output.stat().st_size} sha256={digest} (full)")


if __name__ == "__main__":
    main()
