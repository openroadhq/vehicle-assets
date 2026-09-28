#!/usr/bin/env python3
"""Classify a dated export against its pinned base and local WebP assets.

Derived from the September 17 classifier. REQUESTS_* environment variables
select the date, delta directory, worktree and pinned manifest revision.
"""

from __future__ import annotations

import csv
import os
import datetime as dt
import json
import re
import subprocess
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(os.environ["REQUESTS_DELTA"])
DATA_DIR = ROOT / "data"
RUN_DATE = os.environ["REQUESTS_DATE"]
PRIOR_TRIAGE = ROOT.parent / "triage.csv"
REQUESTS_PATH = DATA_DIR / f"vehicleModelRequests-raw-{RUN_DATE}.json"
AGG_PATH = DATA_DIR / f"vehicleModelRequestsAgg-raw-{RUN_DATE}.json"
ASSET_REPO = Path(os.environ["REQUESTS_WORKTREE"])
MANIFEST_REF = os.environ.get("REQUESTS_BASE", "HEAD")
WORKTREE_V1 = ASSET_REPO / "v1"

JUNK_SLUGS = {
    "na-na",
    "mopar-shi",
    "chud-4-0-67-2067",
    "golf-mk2-cl-fake-gti-1990",
}
GENERIC_WORDS = {"na", "n-a", "unknown", "none", "null", "sedan", "suv", "crossover"}
COMMON_MAKE_ALIASES = {
    "mercades": "mercedes-benz",
    "mercedes": "mercedes-benz",
    "mercedes-benz": "mercedes-benz",
    "mercedes-benz-c": "mercedes-benz",
    "mercedes-benz-s": "mercedes-benz",
    "chevy": "chevrolet",
    "cheverolet": "chevrolet",
    "chengan": "changan",
    "gelly": "geely",
    "vw": "volkswagen",
    "landrover": "land-rover",
    "range-rover": "land-rover",
    "gmc": "gmc",
    "skoda": "skoda",
    "citroen": "citroen",
    "cf-moto": "cf-moto",
    "canam": "can-am",
}
COMMON_MAKES = {
    "abarth", "acura", "aixam", "alfa-romeo", "aprilia", "aston-martin", "audi",
    "baic", "belgee", "bmw", "brillance", "bugatti", "buick", "byd",
    "cadillac", "can-am", "cf-moto", "changan", "chevrolet", "chrysler", "citroen", "perodua",
    "cupra", "dacia", "dodge", "ducati", "engwe", "fiat", "ford", "fuso",
    "gac", "geely", "genesis", "gmc", "harley-davidson", "haval", "holden", "honda",
    "hsv", "hyundai", "infiniti", "iveco", "jaecoo", "jaguar", "jeep", "kawasaki",
    "kayo", "kia", "ktm", "kymco", "lada", "lancia", "land-rover", "lexmoto", "lexus",
    "mahindra", "maserati", "mazda", "mg", "mini", "mitsubishi", "mopar", "mercury",
    "nissan", "oldsmobile", "opel", "peugeot", "polestar", "pontiac", "porsche", "proton",
    "ram", "renault", "rolls-royce", "scania", "scion", "seat", "skoda", "smart", "subaru",
    "suzuki", "tata", "tesla", "toyota", "triumph", "vauxhall", "volkswagen", "volvo", "xev",
    "xpeng", "yamaha",
}
SPECIAL_MODEL_MAKES = {
    "brezza": {"maruti-suzuki"},
    "falcon": {"ford"},
    "golf": {"volkswagen"},
    "gti": {"volkswagen"},
    "h6": {"haval"},
    "kluger": {"toyota"},
    "mustang": {"ford"},
    "tsuru": {"nissan"},
    "xr6": {"ford"},
}


def git_json(path: str) -> dict[str, Any]:
    result = subprocess.run(
        ["git", "-C", str(ASSET_REPO), "show", f"{MANIFEST_REF}:{path}"],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def slug_component(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", folded).strip("-")
    return slug or None


def valid_year(value: Any) -> int | None:
    if isinstance(value, (int, float)) and int(value) == value and 1900 <= int(value) <= 2100:
        return int(value)
    return None


def canonical_make(value: Any, known_makes: set[str]) -> str | None:
    slug = slug_component(value)
    if not slug:
        return None
    if slug in COMMON_MAKE_ALIASES:
        return COMMON_MAKE_ALIASES[slug]
    if slug in known_makes or slug in COMMON_MAKES:
        return slug
    for alias, target in sorted(COMMON_MAKE_ALIASES.items(), key=lambda item: -len(item[0])):
        if slug.startswith(alias + "-"):
            return target
    for make in sorted(known_makes | COMMON_MAKES, key=len, reverse=True):
        if slug == make or slug.startswith(make + "-"):
            return make
    return None


def build_model_index(manifest: dict[str, Any]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = defaultdict(set)
    paths = set(manifest["vehicles"]) | set(manifest["aliases"]) | set(manifest["generations"])
    for path in paths:
        if "/" not in path:
            continue
        make, model = path.split("/", 1)
        model = re.sub(r"-\d{4}$", "", model)
        index[model].add(make)
    for model, makes in SPECIAL_MODEL_MAKES.items():
        index[model].update(makes)
    return index


def parse_flat_slug(slug: str, manifest: dict[str, Any], model_index: dict[str, set[str]]) -> tuple[str, str] | None:
    value = slug_component(slug)
    if not value:
        return None
    value = re.sub(r"^\d{4}-", "", value)
    value = re.sub(r"-\d{4}$", "", value)
    if value == "mk5-gti":
        return "volkswagen", "golf-mk5-gti"
    known_makes = {path.split("/", 1)[0] for path in manifest["vehicles"]}
    prefixes = set(known_makes) | COMMON_MAKES | set(COMMON_MAKE_ALIASES)
    for prefix in sorted(prefixes, key=len, reverse=True):
        if value == prefix or value.startswith(prefix + "-"):
            tail = value[len(prefix):].strip("-")
            if tail:
                return COMMON_MAKE_ALIASES.get(prefix, prefix), tail

    model_hits: list[tuple[int, str, str]] = []
    for model, makes in model_index.items():
        if value == model or value.startswith(model + "-"):
            for make in makes:
                model_hits.append((len(model), make, value[len(model):].strip("-")))
    if model_hits:
        model_hits.sort(reverse=True)
        _, make, tail = model_hits[0]
        return make, value if not tail else value
    return None


def resolve(candidate: str, year: int | None, manifest: dict[str, Any]) -> str | None:
    canonical = canonical_target(candidate, manifest)
    if canonical is None and candidate in manifest["generations"]:
        canonical = candidate
    if canonical is None:
        return None
    generations = manifest["generations"].get(canonical)
    if generations:
        selected = generations[-1]
        if year is not None:
            selected = next((item for item in reversed(generations) if item[0] <= year), generations[0])
        canonical = selected[1]
    return canonical if canonical in manifest["vehicles"] else None


def canonical_target(candidate: str, manifest: dict[str, Any]) -> str | None:
    if candidate in manifest["vehicles"]:
        return candidate
    return manifest["aliases"].get(candidate)


def base_model_and_trim(make: str, tail: str, model_index: dict[str, set[str]]) -> tuple[str, str | None]:
    candidates = [model for model, makes in model_index.items() if make in makes and (tail == model or tail.startswith(model + "-"))]
    if not candidates:
        return tail, None
    model = max(candidates, key=len)
    remainder = tail[len(model):].strip("-")
    return model, remainder or None


def inferred_model_from_trim(make: str, trim: str | None, model_index: dict[str, set[str]]) -> tuple[str, str | None] | None:
    if not trim:
        return None
    matches = [model for model, makes in model_index.items() if make in makes and (trim == model or trim.startswith(model + "-"))]
    if not matches and make == "bmw" and re.match(r"^[1345678]\d{2}", trim):
        return trim[0] + "-series", trim
    if not matches:
        return None
    model = max(matches, key=len)
    remainder = trim[len(model):].strip("-")
    return model, remainder or None


def field_identity(record: dict[str, Any], known_makes: set[str], model_index: dict[str, set[str]]) -> tuple[str, str, str | None, int | None] | None:
    data = record["data"]
    make = canonical_make(data.get("make"), known_makes)
    model = slug_component(data.get("model"))
    trim = slug_component(data.get("trim"))
    if not make or not model:
        return None
    if model in GENERIC_WORDS:
        inferred = inferred_model_from_trim(make, trim, model_index)
        if not inferred:
            return None
        model, inferred_trim = inferred
        trim = inferred_trim
    return make, model, trim, valid_year(data.get("year"))


def identity_variants(record: dict[str, Any], manifest: dict[str, Any], model_index: dict[str, set[str]]) -> list[tuple[str, str, str | None, int | None]]:
    known_makes = {path.split("/", 1)[0] for path in manifest["vehicles"]}
    variants: list[tuple[str, str, str | None, int | None]] = []
    direct = field_identity(record, known_makes, model_index)
    if direct:
        variants.append(direct)

    data = record["data"]
    parsed = parse_flat_slug(data.get("slug", ""), manifest, model_index)
    if parsed:
        make, tail = parsed
        year = valid_year(data.get("year"))
        model = slug_component(data.get("model"))
        trim = slug_component(data.get("trim"))
        if model and (model == make or model.startswith(make + "-") or model in GENERIC_WORDS):
            model = None
        parsed_model, parsed_trim = base_model_and_trim(make, tail, model_index)
        raw_make = canonical_make(data.get("make"), known_makes)
        if raw_make == make and model:
            parsed_model = model
        elif slug_component(data.get("model")) in GENERIC_WORDS and parsed_model == tail:
            parsed_model = None
        if not trim:
            trim = parsed_trim
        if make and parsed_model:
            variants.append((make, parsed_model, trim, year))
        if make and tail and (parsed_model or slug_component(data.get("model")) not in GENERIC_WORDS):
            variants.append((make, tail, None, year))

    deduped: list[tuple[str, str, str | None, int | None]] = []
    for variant in variants:
        if variant not in deduped:
            deduped.append(variant)
    return deduped


def candidate_paths(make: str, model: str, trim: str | None) -> tuple[str, list[str]]:
    base = f"{make}/{model}"
    specific = f"{base}-{trim}" if trim else base
    fallbacks = []
    if trim:
        fallbacks.append(f"{make}/{trim}")
    fallbacks.append(base)
    return specific, fallbacks


def prefix_fallbacks(candidate: str, manifest: dict[str, Any]) -> list[str]:
    if "/" not in candidate:
        return []
    make, rest = candidate.split("/", 1)
    keys = set(manifest["vehicles"]) | set(manifest["aliases"]) | set(manifest["generations"])
    matches = [key for key in keys if key.startswith(make + "/") and rest.startswith(key.split("/", 1)[1] + "-")]
    return sorted(matches, key=len, reverse=True)


def is_explicit_junk(record: dict[str, Any]) -> bool:
    data = record["data"]
    slug = str(data.get("slug", "")).lower()
    if slug in JUNK_SLUGS:
        return True
    make = str(data.get("make", "")).strip().lower()
    model = str(data.get("model", "")).strip().lower()
    return make in {"na", "unknown", "none"} and model in {"na", "unknown", "none"}


def classify(record: dict[str, Any], manifest: dict[str, Any], model_index: dict[str, set[str]]) -> dict[str, Any]:
    if is_explicit_junk(record):
        return {"class": "JUNK", "matched": "", "candidate": "", "alias": None, "variants": []}

    variants = identity_variants(record, manifest, model_index)
    best_missing: str | None = None
    for make, model, trim, year in variants:
        specific, fallbacks = candidate_paths(make, model, trim)
        specific_hit = resolve(specific, year, manifest)
        if specific_hit:
            return {"class": "EXACT", "matched": specific_hit, "candidate": specific, "alias": None, "variants": variants}
        for fallback in fallbacks:
            fallback_hit = resolve(fallback, year, manifest)
            if fallback_hit and fallback != specific:
                fallback_base = canonical_target(fallback, manifest) or fallback
                return {
                    "class": "ALIAS GAP",
                    "matched": f"{specific} -> {fallback_hit}",
                    "candidate": specific,
                    "alias": {specific: fallback_base},
                    "variants": variants,
                }
        for fallback in prefix_fallbacks(specific, manifest):
            fallback_hit = resolve(fallback, year, manifest)
            if fallback_hit:
                fallback_base = canonical_target(fallback, manifest) or fallback
                return {
                    "class": "ALIAS GAP",
                    "matched": f"{specific} -> {fallback_hit}",
                    "candidate": specific,
                    "alias": {specific: fallback_base},
                    "variants": variants,
                }
        if best_missing is None:
            best_missing = f"{make}/{model}"

    if best_missing:
        return {"class": "MISSING", "matched": best_missing, "candidate": best_missing, "alias": None, "variants": variants}
    return {"class": "JUNK", "matched": "", "candidate": "", "alias": None, "variants": variants}


def worktree_v1_slugs() -> set[str]:
    """Every v1/**/*.webp present in the worktree, tracked or not.

    The live renders lane writes files before they are committed, so the
    manifest of record under-reports what actually exists on disk. That lane
    is running WHILE this classifies, so the glob is snapshotted to
    data/worktree-v1-snapshot-<RUN_DATE>.json and every downstream step reads
    the snapshot, never a second glob. Read-only: nothing is written into the
    asset repo.
    """
    if not WORKTREE_V1.is_dir():
        return set()
    slugs = sorted(
        str(path.relative_to(WORKTREE_V1))[: -len(".webp")]
        for path in WORKTREE_V1.rglob("*.webp")
    )
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / f"worktree-v1-snapshot-{RUN_DATE}.json").write_text(
        json.dumps(
            {
                "repo": str(ASSET_REPO),
                "snapshotAt": dt.datetime.now(dt.timezone.utc).isoformat(),
                "count": len(slugs),
                "slugs": slugs,
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return set(slugs)


def augment_with_worktree(manifest: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fold worktree-only assets into the manifest's vehicle set (read-only)."""
    extra = sorted(worktree_v1_slugs() - set(manifest["vehicles"]))
    for slug in extra:
        manifest["vehicles"][slug] = {"source": "worktree"}
    return manifest, extra


def load_records(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))["documents"]


def first_seen_for(group: dict[str, Any]) -> str:
    stamps = [
        record["data"].get("createdAt")
        for record in group["records"]
        if record["data"].get("createdAt")
    ]
    agg = group["agg"]
    if agg:
        for key in ("firstRequestedAt", "lastRequestedAt"):
            if agg["data"].get(key):
                stamps.append(agg["data"][key])
        if agg.get("createTime"):
            stamps.append(agg["createTime"])
    for record in group["records"]:
        if record.get("createTime"):
            stamps.append(record["createTime"])
    return min(stamps) if stamps else ""


def source_fields(group: dict[str, Any]) -> dict[str, Any]:
    source = group["records"][0] if group["records"] else group["agg"]
    data = source["data"]
    return {
        "make": data.get("make"),
        "model": data.get("model"),
        "trim": data.get("trim"),
        "year": data.get("year"),
        "rawText": data.get("rawText") or (group["agg"] or {}).get("data", {}).get("displayName"),
    }


def main() -> None:
    requests = load_records(REQUESTS_PATH)
    aggs = load_records(AGG_PATH)
    manifest = git_json("manifest.json")
    manifest_vehicles_of_record = len(manifest["vehicles"])
    manifest, worktree_extra = augment_with_worktree(manifest)
    aliases = manifest["aliases"]
    model_index = build_model_index(manifest)

    grouped: dict[str, dict[str, Any]] = {}
    for record in requests:
        slug = record["data"]["slug"]
        row = grouped.setdefault(slug, {"slug": slug, "request_count": 0, "uids": set(), "records": [], "agg": None})
        row["request_count"] += 1
        if record["data"].get("uid"):
            row["uids"].add(record["data"]["uid"])
        row["records"].append(record)
    for record in aggs:
        slug = record["data"]["slug"]
        row = grouped.setdefault(slug, {"slug": slug, "request_count": 0, "uids": set(), "records": [], "agg": None})
        row["agg"] = record
        if not row["request_count"]:
            row["request_count"] = int(record["data"].get("requestCount") or 0)

    rows: list[dict[str, Any]] = []
    proposed: dict[str, str] = {}
    for slug in sorted(grouped):
        group = grouped[slug]
        source = group["records"][0] if group["records"] else group["agg"]
        result = classify(source, manifest, model_index)
        if result["alias"]:
            proposed.update(result["alias"])
        rows.append(
            {
                "slug": slug,
                "distinct_users": len(group["uids"]) if group["records"] else "unknown",
                "requests": group["request_count"],
                "class": result["class"],
                "matched": result["matched"],
                "candidate": result["candidate"],
                "alias": result["alias"],
                "agg_request_count": int((group["agg"] or {}).get("data", {}).get("requestCount") or 0),
                "source_documents": len(group["records"]),
                "first_seen": first_seen_for(group),
                "fields": source_fields(group),
            }
        )

    counts = Counter(row["class"] for row in rows)

    triage_path = DATA_DIR / f"triage-full-{RUN_DATE}.csv"
    with triage_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["slug", "distinct users", "class", "matched asset or proposed alias"])
        for row in rows:
            value = row["matched"]
            if row["class"] == "ALIAS GAP":
                value = json.dumps({row["candidate"]: row["matched"].split(" -> ", 1)[1]}, separators=(",", ":"))
            writer.writerow([row["slug"], row["distinct_users"], row["class"], value])

    classified_path = DATA_DIR / f"classified-{RUN_DATE}.json"
    classified_path.write_text(json.dumps(rows, indent=1, sort_keys=True) + "\n", encoding="utf-8")

    proof = {
        "generatedAt": dt.datetime.now(dt.timezone.utc).isoformat(),
        "runDate": RUN_DATE,
        "firestore": {
            "vehicleModelRequestsDocs": len(requests),
            "vehicleModelRequestsDistinctSlugs": len({record["data"]["slug"] for record in requests}),
            "vehicleModelRequestsAggDocs": len(aggs),
            "vehicleModelRequestsAggDistinctSlugs": len({record["data"]["slug"] for record in aggs}),
            "unionDistinctSlugs": len(rows),
            "aggOnlySlugs": sum(1 for row in rows if row["source_documents"] == 0),
        },
        "assets": {
            "repo": str(ASSET_REPO),
            "ref": MANIFEST_REF,
            "manifestVehiclesOfRecord": manifest_vehicles_of_record,
            "worktreeOnlyV1Assets": worktree_extra,
            "vehiclesAfterWorktreeMerge": len(manifest["vehicles"]),
            "manifestAliases": len(aliases),
            "manifestGenerations": len(manifest["generations"]),
        },
        "counts": dict(sorted(counts.items())),
        "proposedAliasCount": len(proposed),
        "outputs": {"triageFull": str(triage_path), "classified": str(classified_path)},
    }
    (DATA_DIR / f"triage-proof-{RUN_DATE}.json").write_text(json.dumps(proof, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({"rows": len(rows), "counts": dict(sorted(counts.items())), "proposedAliases": len(proposed), "worktreeExtra": len(worktree_extra)}, sort_keys=True))


if __name__ == "__main__":
    main()
