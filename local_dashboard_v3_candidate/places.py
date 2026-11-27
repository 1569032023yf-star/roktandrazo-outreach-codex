"""Read the bundled Census catalogue without changing the production database."""
import csv
from functools import lru_cache
import io
from pathlib import Path
import re
from zipfile import ZipFile

ARCHIVE = Path(__file__).parent / 'census_places_2025.zip'
SOURCE = 'https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.2025.html'


def key(name):
    return ' '.join(name.casefold().split())


def short_name(name):
    return re.sub(r'\s+(?:city and borough|city and county|municipality|city|town|village|borough|CDP)$', '', name, flags=re.I)


@lru_cache(maxsize=1)
def load():
    with ZipFile(ARCHIVE) as archive:
        with archive.open('2025_Gaz_place_national.txt') as raw:
            rows = list(csv.DictReader(io.TextIOWrapper(raw, encoding='utf-8'), delimiter='|'))
    return tuple({'state': r['USPS'], 'id': r['GEOID'], 'official': r['NAME'],
                  'name': short_name(r['NAME'])} for r in rows)


def for_state(code, catalog):
    if not re.fullmatch(r'[A-Z]{2}', code):
        raise ValueError('invalid state')
    places = [p.copy() for p in load() if p['state'] == code]
    by_name = {}
    queue = {}
    for p in places:
        by_name.setdefault(key(p['name']), []).append(p)
    for c in catalog or []:
        if c['state'] == code:
            queue.setdefault(key(c['city']), []).append(c)
    used = set()
    for p in places:
        k = key(p['name'])
        matches = queue.get(k, [])
        if len(matches) == 1 and len(by_name[k]) == 1:
            c = matches[0]
            used.add(c['id'])
            p['queue_id'] = c['id']
            p['queue_status'] = c.get('status')
            p['completed_at'] = c.get('completed_at')
            p['query_completed'] = c.get('query_completed')
            p['query_recorded'] = c.get('query_recorded')
            p['candidates'] = c.get('candidates')
            p['last_success_at'] = c.get('last_success_at')
            # A candidate row or a generic progress timestamp cannot establish
            # that a real search ran. Keep each observed evidence type distinct.
            p['history'] = ('recorded' if c.get('query_recorded') or c.get('query_completed')
                            else 'candidates' if c.get('candidates')
                            else 'activity' if c.get('last_success_at')
                            else 'task' if c.get('started_at') else 'unknown')
        else:
            p['history'] = 'ambiguous' if matches else 'unknown'
    for matches in queue.values():
        for c in matches:
            if c['id'] not in used:
                places.append({'state': code, 'id': 'queue:' + str(c['id']), 'name': c['city'],
                               'official': c['city'] + '（系统城市，需核对）', 'queue_id': c['id'],
                               'history': 'ambiguous', 'queue_status': c.get('status'),
                               'completed_at': c.get('completed_at'),
                               'query_completed': c.get('query_completed'), 'query_recorded': c.get('query_recorded'),
                               'candidates': c.get('candidates'), 'last_success_at': c.get('last_success_at')})
    return sorted(places, key=lambda p: (key(p['name']), p['id']))
