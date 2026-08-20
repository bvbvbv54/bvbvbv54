#!/usr/bin/env python3
"""Replace the activity generator's commit-language donut with a code-byte donut."""

from __future__ import annotations

import math
import json
import os
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path


START_MARKER = '<g transform="translate(40, 520)">'
END_MARKER = '<g><text style="font-size: 32px; font-weight: bold;" x="384"'
OTHER_COLOR = "#444444"


def github_languages() -> list[tuple[str, int, str]]:
    """Read every owned, non-fork repository's current language bytes."""
    token = os.environ.get("GITHUB_TOKEN")
    expected_owner = os.environ.get("GITHUB_OWNER")
    if not token:
        raise RuntimeError("GITHUB_TOKEN is required for live language data")

    query = """
    query($cursor: String) {
      viewer {
        login
        repositories(
          first: 100,
          after: $cursor,
          ownerAffiliations: [OWNER],
          isFork: false,
          orderBy: {field: NAME, direction: ASC}
        ) {
          pageInfo { hasNextPage endCursor }
          nodes {
            languages(first: 100, orderBy: {field: SIZE, direction: DESC}) {
              edges { size node { name color } }
            }
          }
        }
      }
    }
    """
    totals: dict[str, int] = defaultdict(int)
    colors: dict[str, str] = {}
    cursor = None
    owner = None
    repo_count = 0

    while True:
        payload = json.dumps({"query": query, "variables": {"cursor": cursor}}).encode()
        request = urllib.request.Request(
            "https://api.github.com/graphql",
            data=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "bvbvbv54-profile-language-donut",
            },
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
        if result.get("errors"):
            raise RuntimeError(f"GitHub GraphQL error: {result['errors']}")

        viewer = result["data"]["viewer"]
        owner = viewer["login"]
        repositories = viewer["repositories"]
        for repository in repositories["nodes"]:
            repo_count += 1
            for edge in repository["languages"]["edges"]:
                name = edge["node"]["name"]
                totals[name] += edge["size"]
                colors[name] = edge["node"]["color"] or OTHER_COLOR

        page = repositories["pageInfo"]
        if not page["hasNextPage"]:
            break
        cursor = page["endCursor"]

    if expected_owner and owner.casefold() != expected_owner.casefold():
        raise RuntimeError(f"token owner {owner!r} does not match {expected_owner!r}")
    if not totals:
        raise RuntimeError("GitHub returned no language data")

    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)
    top = [(name, size, colors[name]) for name, size in ranked[:5]]
    remainder = sum(size for _, size in ranked[5:])
    if remainder:
        top.append(("Other", remainder, OTHER_COLOR))
    print(f"GITHUB_LANGUAGE_DATA owner={owner} repos={repo_count} languages={len(ranked)}")
    return top


def point(radius: float, angle: float) -> tuple[float, float]:
    radians = math.radians(angle)
    return radius * math.cos(radians), radius * math.sin(radians)


def donut_path(start: float, end: float) -> str:
    outer, inner = 117.0, 65.0
    x1, y1 = point(outer, start)
    x2, y2 = point(outer, end)
    x3, y3 = point(inner, end)
    x4, y4 = point(inner, start)
    large = 1 if end - start > 180 else 0
    return (
        f"M{x1:.3f},{y1:.3f}A{outer:g},{outer:g},0,{large},1,{x2:.3f},{y2:.3f}"
        f"L{x3:.3f},{y3:.3f}A{inner:g},{inner:g},0,{large},0,{x4:.3f},{y4:.3f}Z"
    )


def build_donut(languages: list[tuple[str, int, str]]) -> str:
    total = sum(value for _, value, _ in languages)
    legend = []
    paths = []
    angle = -90.0

    for index, (name, value, color) in enumerate(languages):
        percent = value / total * 100
        y = 10 + index * 32.5
        legend.append(
            f'<rect x="0" y="{y:.2f}" width="21.67" height="21.67" '
            f'fill="{color}" stroke="#00000f" stroke-width="1px"></rect>'
            f'<text dominant-baseline="middle" x="26" y="{y + 10.84:.2f}" '
            f'fill="#eeeeff" font-size="19px">{name} {percent:.2f}%</text>'
        )
        next_angle = angle + value / total * 360
        paths.append(
            f'<path d="{donut_path(angle, next_angle)}" style="fill: {color};" '
            f'stroke="#00000f" stroke-width="2px"><title>{name} {percent:.2f}%</title></path>'
        )
        angle = next_angle

    return (
        '<g transform="translate(40, 520)">'
        '<g transform="translate(273, 0)">'
        + "".join(legend)
        + '</g><g transform="translate(130, 130)">'
        + '<animateTransform id="language-donut-rotation" attributeName="transform" '
        + 'type="rotate" from="0 0 0" to="360 0 0" begin="3s" dur="24s" '
        + 'calcMode="linear" repeatCount="indefinite" additive="sum"></animateTransform>'
        + "".join(paths)
        + '</g></g>'
    )


def patch_svg(path: Path, languages: list[tuple[str, int, str]]) -> bool:
    content = path.read_text(encoding="utf-8")
    start = content.find(START_MARKER)
    end = content.find(END_MARKER, start)
    if start < 0 or end < 0:
        raise RuntimeError(f"donut markers not found in {path}")
    updated = content[:start] + build_donut(languages) + content[end:]
    changed = updated != content
    if changed:
        path.write_text(updated, encoding="utf-8", newline="")
    return changed


def main() -> int:
    languages = github_languages()
    paths = [Path(arg) for arg in sys.argv[1:]]
    if not paths:
        paths = sorted(Path("profile-3d-contrib").glob("*.svg"))
    if not paths:
        print("ERROR: no profile SVGs found", file=sys.stderr)
        return 1

    changed = 0
    for path in paths:
        changed += int(patch_svg(path, languages))
    total = sum(value for _, value, _ in languages)
    print(f"LANGUAGE_DONUT_OK files={len(paths)} changed={changed} bytes={total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
