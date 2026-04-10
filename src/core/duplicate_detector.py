"""
HabteX Adder - Duplicate / Multi-Account Detector

Detects clusters like: mash1, mash2, mash3 ... mash50
Logic:
  1. For every member, derive a "prefix" by stripping trailing digits + whitespace
     from their display name (first_name + last_name).
  2. Count how many members share each prefix.
  3. If a prefix repeats >= threshold times → flag that cluster.

Also checks usernames the same way (e.g. user_bot1, user_bot2 ...).

Returns a DuplicateReport with all flagged clusters and a clean summary.
"""

import re
from dataclasses import dataclass, field
from typing import List, Dict, Optional


@dataclass
class MemberInfo:
    user_id: int
    first_name: str
    last_name: str
    username: Optional[str]
    phone: Optional[str]

    @property
    def display_name(self) -> str:
        parts = [self.first_name or '', self.last_name or '']
        return ' '.join(p for p in parts if p).strip()


@dataclass
class DuplicateCluster:
    prefix: str
    source: str          # 'name' or 'username'
    members: List[MemberInfo] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.members)

    def summary(self) -> str:
        sample = ', '.join(
            m.display_name or m.username or str(m.user_id)
            for m in self.members[:5]
        )
        more = f' ... +{self.count - 5} more' if self.count > 5 else ''
        return f'[{self.source.upper()}] "{self.prefix}*" × {self.count}: {sample}{more}'


@dataclass
class DuplicateReport:
    total_members: int
    clusters: List[DuplicateCluster] = field(default_factory=list)
    threshold: int = 20

    @property
    def flagged_count(self) -> int:
        return sum(c.count for c in self.clusters)

    @property
    def has_flags(self) -> bool:
        return bool(self.clusters)

    def text_summary(self) -> str:
        if not self.clusters:
            return f'✅ No multi-account clusters found in {self.total_members} members.'
        lines = [
            f'⚠ {len(self.clusters)} cluster(s) detected '
            f'({self.flagged_count}/{self.total_members} members flagged):'
        ]
        for c in sorted(self.clusters, key=lambda x: -x.count):
            lines.append(f'  • {c.summary()}')
        return '\n'.join(lines)


# ── Core detection ────────────────────────────────────────────────────────────

_TRAILING_DIGITS_RE = re.compile(r'[\d\s_\-\.]+$')


def _extract_prefix(text: str, min_len: int) -> Optional[str]:
    """Strip trailing digits/separators; return prefix if long enough."""
    if not text:
        return None
    prefix = _TRAILING_DIGITS_RE.sub('', text).strip()
    return prefix if len(prefix) >= min_len else None


def detect_duplicates(
    members: List[MemberInfo],
    threshold: int = 20,
    min_prefix_len: int = 3,
) -> DuplicateReport:
    """
    Analyse member list and return a DuplicateReport.

    Args:
        members:         list of MemberInfo objects
        threshold:       minimum repeat count to flag a cluster (default 20)
        min_prefix_len:  ignore prefixes shorter than this (default 3)
    """
    name_map: Dict[str, List[MemberInfo]] = {}
    user_map: Dict[str, List[MemberInfo]] = {}

    for m in members:
        # ── by display name
        name_prefix = _extract_prefix(m.display_name.lower(), min_prefix_len)
        if name_prefix:
            name_map.setdefault(name_prefix, []).append(m)

        # ── by username
        if m.username:
            uname = m.username.lstrip('@').lower()
            u_prefix = _extract_prefix(uname, min_prefix_len)
            if u_prefix:
                user_map.setdefault(u_prefix, []).append(m)

    clusters: List[DuplicateCluster] = []

    for prefix, group in name_map.items():
        if len(group) >= threshold:
            clusters.append(DuplicateCluster(prefix=prefix, source='name', members=group))

    for prefix, group in user_map.items():
        if len(group) >= threshold:
            # avoid double-counting same cluster already caught by name
            already = any(c.prefix == prefix and c.source == 'username' for c in clusters)
            if not already:
                clusters.append(DuplicateCluster(prefix=prefix, source='username', members=group))

    return DuplicateReport(
        total_members=len(members),
        clusters=clusters,
        threshold=threshold,
    )


# ── Telethon helper ───────────────────────────────────────────────────────────

def members_from_telethon(participants) -> List[MemberInfo]:
    """Convert a Telethon participants list to MemberInfo objects."""
    result = []
    for p in participants:
        result.append(MemberInfo(
            user_id=p.id,
            first_name=p.first_name or '',
            last_name=p.last_name or '',
            username=p.username,
            phone=getattr(p, 'phone', None),
        ))
    return result
