import sys
import json
import os
import subprocess


def serena_process_running():
    """실제 serena.exe 프로세스가 떠있는지 확인. 확인 불가 시 None."""
    try:
        result = subprocess.run(
            ["tasklist", "/fi", "imagename eq serena.exe", "/fo", "csv", "/nh"],
            capture_output=True,
            text=True,
            timeout=2,
        )
        return "serena.exe" in result.stdout
    except Exception:
        return None


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    cwd = (
        data.get("workspace", {}).get("current_dir")
        or data.get("cwd")
        or os.getcwd()
    )
    folder_name = os.path.basename(cwd.rstrip("\\/"))
    has_config = os.path.isdir(os.path.join(cwd, ".serena"))

    if not has_config:
        icon, label = "⚪", "Serena OFF"  # 백색원 = 설정 자체 없음
    else:
        running = serena_process_running()
        if running is True:
            icon, label = "\U0001f7e2", "Serena ON"  # 녹색원 = 설정+프로세스 둘 다 확인
        elif running is False:
            icon, label = "\U0001f7e1", "Serena 이상"  # 황색원 = 설정만 있고 프로세스 없음
        else:
            icon, label = "❓", "Serena 확인불가"  # 물음표 = tasklist 자체 실패

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"{folder_name} | {icon} {label}")


if __name__ == "__main__":
    main()
