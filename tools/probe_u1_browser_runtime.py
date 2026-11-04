"""Bounded offline browser fixture / 有总超时的离线浏览器测试。"""
import argparse
import json
import os
from pathlib import Path
import sys


def child(events):
    def event(stage):
        with Path(events).open('a',encoding='utf-8') as stream:
            stream.write(json.dumps(dict(stage=stage))+'\n')
            stream.flush()
            os.fsync(stream.fileno())
    event('CHILD_STARTED')
    from playwright.sync_api import sync_playwright
    event('PLAYWRIGHT_IMPORTED')
    with sync_playwright() as p:
        event('DRIVER_STARTED')
        browser = p.chromium.launch(headless=True,chromium_sandbox=True,timeout=10000)
        event('BROWSER_STARTED')
        context = browser.new_context(offline=True)
        context.route('**/*',lambda route:route.abort())
        page = context.new_page()
        page.set_content('<title>U1 local fixture</title>')
        assert page.title() == 'U1 local fixture'
        event('LOCAL_FIXTURE_PASSED')
        browser.close()
    event('CLOSED')


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--child',action='store_true')
    for name in ('python','browsers','events','output'):
        p.add_argument('--'+name)
    a = p.parse_args()
    if a.child:
        child(a.events)
    else:
        from tools.prepare_u1_python_runtime import sha
        from autonomy.process_job import run_tree
        events, output = Path(a.events).resolve(), Path(a.output).resolve()
        if events.exists() or output.exists():
            raise ValueError('NEW_EVIDENCE_PATHS_REQUIRED')
        exe = Path(a.python).resolve()
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(Path(a.browsers).resolve())
        result = dict(fixture_only=True,provider_requests=0,passed=False,
                      python_sha256=sha(exe.read_bytes()))
        try:
            r = run_tree([str(exe),'-I','-B',str(Path(__file__).resolve()),
                          '--child','--events',str(events)],
                         cwd=str(exe.parent),timeout=25,cleanup_timeout=8)
            result.update(returncode=r.returncode,stdout=r.stdout,stderr=r.stderr,
                          cleanup_verified=r.cleanup_verified,passed=r.returncode==0)
        except Exception as error:
            result.update(exception_type=type(error).__name__,
                          cleanup_verified=getattr(error,'cleanup_verified',None),
                          cleanup_errors=getattr(error,'cleanup_errors',None))
        result['stages'] = [json.loads(row) for row in events.read_text(encoding='utf-8').splitlines()] if events.exists() else []
        output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result))
        raise SystemExit(0 if result['passed'] else 1)
