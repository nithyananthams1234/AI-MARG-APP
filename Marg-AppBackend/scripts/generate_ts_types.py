"""Generate TypeScript types for the frontend from the backend OpenAPI schema.

Usage (from Marg-AppBackend):
    python scripts/generate_ts_types.py ../Marg-AppFrontend/src/lib/api/generated.ts

Keeps the frontend's request/response types in lock-step with the real
backend contract (no hand-written, drifting copies).
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/x")
os.environ.setdefault("JWT_SECRET_KEY", "type-generation-only")

from app.main import app  # noqa: E402


def ts_type(schema: dict) -> str:
    if "$ref" in schema:
        return schema["$ref"].split("/")[-1]
    if "anyOf" in schema:
        parts = [ts_type(s) for s in schema["anyOf"]]
        return " | ".join(dict.fromkeys(parts))
    if "allOf" in schema and len(schema["allOf"]) == 1:
        return ts_type(schema["allOf"][0])
    if "enum" in schema:
        return " | ".join(f"'{v}'" if isinstance(v, str) else str(v) for v in schema["enum"])
    if "const" in schema:
        v = schema["const"]
        return f"'{v}'" if isinstance(v, str) else str(v)
    t = schema.get("type")
    if t == "null":
        return "null"
    if t == "string":
        return "string"
    if t in ("integer", "number"):
        return "number"
    if t == "boolean":
        return "boolean"
    if t == "array":
        inner = ts_type(schema.get("items", {}))
        return f"({inner})[]" if "|" in inner else f"{inner}[]"
    if t == "object":
        extra = schema.get("additionalProperties")
        if isinstance(extra, dict) and extra:
            return f"Record<string, {ts_type(extra)}>"
        return "Record<string, unknown>"
    return "unknown"


def main(out_path: str) -> None:
    spec = app.openapi()
    schemas = spec["components"]["schemas"]
    lines = [
        "// AUTO-GENERATED from the MARG backend OpenAPI schema.",
        "// Do not edit by hand: run `python scripts/generate_ts_types.py` in Marg-AppBackend.",
        "",
    ]
    for name in sorted(schemas):
        schema = schemas[name]
        if "enum" in schema:
            lines.append(f"export type {name} = {ts_type(schema)};\n")
            continue
        props = schema.get("properties")
        if not props:
            lines.append(f"export type {name} = {ts_type(schema)};\n")
            continue
        required = set(schema.get("required", []))
        lines.append(f"export interface {name} {{")
        for prop, ps in props.items():
            opt = "" if prop in required else "?"
            lines.append(f"  {prop}{opt}: {ts_type(ps)};")
        lines.append("}\n")
    with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(lines))
    print(f"Wrote {len(schemas)} types to {out_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "generated.ts")
