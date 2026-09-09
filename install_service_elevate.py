"""
BD Execution Host — Self-Elevating Installer
Runs as non-admin, triggers UAC to re-run as admin.
After elevation, installs the service via pywin32 SCM API.
"""
import ctypes, os, sys, time, subprocess

SERVICE_NAME = "BDExecutionHost"
BIN_PATH = r"C:\Users\15690\.workbuddy\binaries\python\versions\3.13.12\python.exe C:\Users\15690\WorkBuddy\2026-06-05-15-31-42\roktandrazo-outreach\bd_execution_host_service.py"


def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False


def install_service():
    """Install and start the Windows Service using pywin32 SCM API."""
    print("[1/5] Removing existing service...")
    try:
        import win32service, win32serviceutil, pywintypes
        try:
            win32serviceutil.StopService(SERVICE_NAME)
            time.sleep(2)
        except:
            pass
        try:
            hs = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_ALL_ACCESS)
            svc = win32service.OpenService(hs, SERVICE_NAME, win32service.SERVICE_ALL_ACCESS)
            win32service.DeleteService(svc)
            svc.Close()
            hs.Close()
            print("  Existing service removed")
        except pywintypes.error as e:
            if e.winerror != 1060:
                print(f"  Note: {e}")
    except Exception as e:
        print(f"  Note: {e}")

    print("[2/5] Creating service...")
    import win32service, pywintypes
    hs = win32service.OpenSCManager(None, None, win32service.SC_MANAGER_CREATE_SERVICE)
    svc = win32service.CreateService(
        hs, SERVICE_NAME, "BD Execution Host",
        win32service.SERVICE_ALL_ACCESS,
        win32service.SERVICE_WIN32_OWN_PROCESS,
        win32service.SERVICE_AUTO_START,
        win32service.SERVICE_ERROR_NORMAL,
        BIN_PATH,
        None, None, None, None, None,
    )
    print("  Service created: Auto-start, LocalSystem")

    print("[3/5] Configuring recovery...")
    try:
        fap = win32service.SERVICE_FAILURE_ACTIONS()
        fap.dwResetPeriod = 86400
        fap.cActions = 3
        fap.lpsaActions = [(1, 60000), (1, 60000), (1, 60000)]
        win32service.ChangeServiceConfig2(svc, 2, fap)
        print("  Recovery: Restart after 60s x3")
    except:
        print("  Recovery config skipped")

    svc.Close()
    hs.Close()

    print("[4/5] Starting service...")
    import win32serviceutil
    win32serviceutil.StartService(SERVICE_NAME)
    time.sleep(3)
    status = win32serviceutil.QueryServiceStatus(SERVICE_NAME)
    names = {1: "STOPPED", 2: "START_PENDING", 3: "STOP_PENDING", 4: "RUNNING"}
    print(f"  Status: {names.get(status[1], status[1])}")

    print("[5/5] Done!")
    print()
    print("Service BDExecutionHost installed and started.")
    print("Run 'python bd_execution_host_service.py status' to check.")


def main():
    if is_admin():
        print("Running as Administrator — installing service...")
        install_service()
        input("\nPress Enter to close...")
    else:
        print("Requesting Administrator privileges...")
        print("A UAC prompt will appear. Please click Yes.")
        # Re-run this script with elevation
        result = ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f'"{__file__}"', None, 5  # SW_SHOW
        )
        if result > 32:
            print("UAC approved — installation in progress in elevated window.")
        else:
            print(f"UAC declined or failed (code {result}).")
            print("You can manually run this script as Administrator:")
            print(f'  Right-click → Run as Administrator on: {__file__}')
            input("\nPress Enter to close...")


if __name__ == "__main__":
    main()
