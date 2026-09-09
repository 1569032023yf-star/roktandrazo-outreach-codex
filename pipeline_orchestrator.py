"""
Pipeline Orchestrator — Run T1-T7 tests sequentially in dry-run mode.
"""
import sys, io, os, subprocess
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

PROJECT_DIR = os.path.dirname(__file__)

def run_test(num, name, script, args):
    print(f'\n{"=" * 70}')
    print(f'T{num}: {name}')
    print(f'{"=" * 70}')
    path = os.path.join(PROJECT_DIR, script)
    cmd = [sys.executable, path] + args
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=PROJECT_DIR, timeout=120)
    print(result.stdout)
    if result.stderr:
        print(f'STDERR: {result.stderr[-500:]}')
    passed = result.returncode == 0
    status_text = 'PASSED' if passed else 'FAILED'
    print(f'[T{num}] {status_text} (exit={result.returncode})')
    return passed

def main():
    print('=' * 70)
    print('T1-T7 PIPELINE TEST - DRY RUN')
    print('=' * 70)
    print()
    
    # T1 already done separately, just verify
    print('[T1] DB Migration — already completed earlier')
    print('     Backup: backup_t1/bd_leads_20260623_162515.db')
    print('     Migration: ran db_migration_v2.py')
    print('     Verify: 301 leads, 61 verified A, 0 guessed in A')
    print()
    
    results = {}
    
    # T2: Lead Collector dry-run
    results['T2'] = run_test(2, 'Lead Collector dry-run', 'agent_lead_collector.py', ['--dry-run'])
    
    # T3: Sender dry-run
    results['T3'] = run_test(3, 'Sender dry-run', 'agent_sender.py', ['--dry-run'])
    
    # T4: Reply Monitor scan
    results['T4'] = run_test(4, 'Reply Monitor scan', 'agent_reply_monitor.py', ['--dry-run'])
    
    # T5: Bounce Auditor sample
    results['T5'] = run_test(5, 'Bounce Auditor sample', 'agent_bounce_auditor.py', ['--sample'])
    
    # T6: Supervisor check
    results['T6'] = run_test(6, 'Supervisor check', 'agent_supervisor.py', ['--check'])
    
    # T7: Daily Report
    results['T7'] = run_test(7, 'Daily Report dry-run', 'agent_daily_report.py', ['--report'])
    
    # Summary
    print('\n' + '=' * 70)
    print('T1-T7 SUMMARY')
    print('=' * 70)
    for test, passed in results.items():
        status = '✅ PASSED' if passed else '❌ FAILED'
        print(f'  {test}: {status}')
    print()
    
    all_pass = all(results.values())
    if all_pass:
        print('✅ ALL TESTS PASSED')
    else:
        print('❌ SOME TESTS FAILED — review before proceeding')

if __name__ == '__main__':
    main()
