"""Deterministic intent-aware ranking and compact conversation bundles."""

import re
from math import log

_WORD = re.compile(r"[\w]+", re.UNICODE)
_CLOCK = re.compile(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b", re.IGNORECASE)
_DATE_RANGE = re.compile(r"\b(?:19|20)\d{2}\s*(?:-|–|—|to|through)\s*(?:19|20)\d{2}\b",
                         re.IGNORECASE)
_STOP = frozenset({
    "a", "about", "an", "and", "are", "did", "do", "does", "earlier", "from", "i", "in",
    "is", "it", "me", "memory", "my", "of", "on", "our", "please", "remember", "said",
    "tell", "that", "the", "this", "to", "was", "we", "what", "when", "where", "which",
    "who", "you", "your",
})
_LOW_VALUE = frozenset({
    "any", "both", "can", "could", "excited", "for", "get", "getting", "how", "look",
    "looking", "many", "new", "some", "suggest", "tip", "visit", "weekend",
})
_CANONICAL = {
    "activities": "activity", "avoided": "avoid", "avoiding": "avoid", "avoids": "avoid",
    "bachelors": "bachelor", "breaks": "break", "compared": "compare", "compares": "compare",
    "comparing": "compare", "comparison": "compare", "coupons": "coupon",
    "completed": "complete", "completing": "complete", "completion": "complete",
    "counts": "count", "days": "day", "degrees": "degree", "durations": "duration",
    "difference": "compare", "differences": "compare", "different": "compare",
    "events": "event", "guitars": "guitar", "highschool": "school",
    "lasted": "last", "lasting": "last", "lasts": "last",
    "leading": "lead", "leads": "lead", "led": "lead", "locations": "location",
    "masters": "master", "meeting": "meet", "meets": "meet", "met": "meet",
    "months": "month",
    "preference": "prefer", "preferences": "prefer", "preferred": "prefer", "prefers": "prefer",
    "projects": "project", "recommendations": "recommend", "recommended": "recommend",
    "recommending": "recommend", "redeemed": "redeem", "redeeming": "redeem",
    "redeems": "redeem", "replaced": "replace", "replacing": "replace",
    "stores": "store", "suggested": "suggest",
    "suggesting": "suggest", "suggestions": "suggest", "tips": "tip",
    "upgraded": "upgrade", "upgrading": "upgrade", "used": "use", "uses": "use",
    "using": "use", "weeks": "week", "years": "year",
}
_RECOMMEND = frozenset({"compare", "evaluate", "new", "recommend", "replace", "suggest",
                        "tip", "upgrade"})
_COMPARE = frozenset({"compare", "evaluate", "replace", "upgrade"})
_PREFERENCE = frozenset({"avoid", "constraint", "prefer", "scope", "time"})
_QUANTIFY = frozenset({"count", "day", "duration", "month", "week", "year"})
_EDUCATION = frozenset({"college", "complete", "degree", "education", "school", "stage",
                        "timeline", "training", "university"})
_STAGES = frozenset({"associate", "bachelor", "college", "degree", "high", "master",
                     "school", "undergraduate", "university"}) | _QUANTIFY
_CONSTRAINT = frozenset({"avoid", "prefer", "scope"})
_TIME = frozenset({"afternoon", "evening", "midday", "morning", "night", "noon",
                   "time", "weekday", "weekend"})
_COMPARISON = {
    "comparison_current": frozenset({"current", "existing", "have", "own"}),
    "comparison_target": frozenset({"change", "desired", "replace", "target", "upgrade", "want"}),
    "comparison_usage": frozenset({"daily", "practice", "use", "usage", "work"}),
    "comparison_fit": frozenset({"comfort", "feel", "fit", "grip", "physical", "size", "weight"}),
    "comparison_performance": frozenset({"accuracy", "battery", "performance", "power", "quality",
                                          "range", "speed"}),
    "comparison_preference": frozenset({"avoid", "prefer"}),
}
_INTERNAL_MARKERS = frozenset(_COMPARISON) | {"stage_fact"}


def ranked_rows(rows, query, temporal_terms):
    base, intent = _query_parts(query)
    terms = base | intent
    if not terms:
        return []
    documents = tuple(_document_terms(row[4]) | temporal_terms(row[5]) for row in rows)
    frequency = {term: sum(term in document for document in documents) for term in terms}
    ranked = []
    for row, document in zip(rows, documents):
        matched = tuple(sorted(terms & document))
        if matched:
            score = _relevance(row, matched, frequency, len(rows), intent - base)
            visible = tuple(term for term in matched if term not in _INTERNAL_MARKERS)
            ranked.append((score, row[3] == "user", row[5], row[6], row, visible))
    ranked.sort(key=lambda item: item[:4], reverse=True)
    return ranked


def bundled_candidates(ranked, rows, limit):
    groups = {}
    for item in ranked:
        groups.setdefault(item[4][1], []).append(item)
    values, selected, seen = tuple(groups.values()), [], set()
    pool_limit = max(limit * 4, limit + 8)
    leaders = values[:2]
    if leaders:
        group = leaders[0]
        _append(selected, seen, group[0][4], group[0][5], "conversation_turn", pool_limit)
    if len(leaders) > 1 and limit > 2:
        group = leaders[1]
        _append(selected, seen, group[0][4], group[0][5], "conversation_turn", pool_limit)
    if leaders:
        _add_bundle(selected, seen, _companions(leaders[0], rows), 2, pool_limit)
    if len(leaders) > 1 and limit <= 2:
        group = leaders[1]
        _append(selected, seen, group[0][4], group[0][5], "conversation_turn", pool_limit)
    if len(leaders) > 1:
        _add_bundle(selected, seen, _companions(leaders[1], rows), 1, pool_limit)
    for group in values[2:]:
        _append(selected, seen, group[0][4], group[0][5], "conversation_turn", pool_limit)
    _round_robin(selected, seen, values, 1, pool_limit)
    for group in values:
        _add_bundle(selected, seen, _companions(group, rows), 2, pool_limit)
    for item in ranked:
        _append(selected, seen, item[4], item[5], "conversation_turn", pool_limit)
    return selected


def _companions(group, rows):
    seed, direct = group[0][4], {(item[4][1], item[4][2]): item for item in group}
    session = [row for row in rows if row[1] == seed[1] and row[2] != seed[2]]
    key = lambda row: (abs(row[6] - seed[6]), len(row[4]), -row[6])
    direct_users = [item[4] for item in group[1:] if item[4][3] == "user"]
    direct_ids = {(row[1], row[2]) for row in direct_users}
    users = sorted((row for row in session if row[3] == "user" and
                    (row[1], row[2]) not in direct_ids), key=key)
    assistants = sorted((row for row in session if row[3] == "assistant"), key=key)
    ordered = direct_users + users + assistants
    return tuple(_candidate(row, direct) for row in ordered)


def _candidate(row, direct):
    item = direct.get((row[1], row[2]))
    return (row, item[5], "conversation_turn") if item else (row, (), "same_session_context")


def _add_bundle(selected, seen, candidates, count, limit):
    added = 0
    for row, matched, provenance in candidates:
        if _append(selected, seen, row, matched, provenance, limit):
            added += 1
        if added >= count:
            return


def _round_robin(selected, seen, groups, index, limit):
    for group in groups:
        if index < len(group):
            item = group[index]
            _append(selected, seen, item[4], item[5], "conversation_turn", limit)


def _append(selected, seen, row, matched, provenance, limit):
    identity = (row[1], row[2])
    if len(selected) >= limit or identity in seen:
        return False
    selected.append((row, matched, provenance))
    seen.add(identity)
    return True


def _query_parts(value):
    raw = _tokens(value)
    strong = raw - _STOP - _LOW_VALUE
    base = strong or raw - _STOP
    return frozenset(base), _intent(raw)


def _document_terms(value):
    raw = _tokens(value)
    result = set(raw - _STOP)
    if raw & _CONSTRAINT:
        result.add("constraint")
    if raw & _TIME or _CLOCK.search(value):
        result.update({"constraint", "time"})
    if _DATE_RANGE.search(value):
        result.update({"duration", "stage_fact", "timeline"})
    for marker, terms in _COMPARISON.items():
        if raw & terms:
            result.add(marker)
    return frozenset(result)


def _intent(raw):
    result = set()
    if raw & _RECOMMEND:
        result.update(_PREFERENCE)
    if raw & _COMPARE:
        result.update(_COMPARISON)
    if "total" in raw or "duration" in raw or "count" in raw:
        result.update(_QUANTIFY)
    if "how" in raw and raw & {"long", "many"}:
        result.update(_QUANTIFY)
    if raw & _EDUCATION:
        result.update(_STAGES | {"stage_fact", "timeline"})
    return frozenset(result)


def _tokens(value):
    return {_CANONICAL.get(token, token) for token in _WORD.findall(value.casefold())
            if len(token) > 1}


def _relevance(row, matched, frequency, document_count, intent_only):
    informative = sum(log((document_count + 1) / (frequency[term] + 0.5)) + 1
                      if term not in intent_only else
                      0.45 * (log((document_count + 1) / (frequency[term] + 0.5)) + 1)
                      for term in matched)
    length_penalty = 1 + max(0, len(_WORD.findall(row[4])) - 12) / 50
    role_weight = 1.5 if row[3] == "user" else 1
    return informative * role_weight / length_penalty + (0.75 if row[3] == "user" else 0)
