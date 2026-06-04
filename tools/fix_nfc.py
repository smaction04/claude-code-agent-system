#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""한글 경로 NFC/NFD 정규화 가드.

윈도우/한국어 입력 = NFC(완성형), 맥·일부 zip·클라우드 = NFD(자모 분리).
섞이면 같은 이름이 두 개처럼 잡혀 "파일 없음(Exit 1)" 발생.

  resolve <path>   : 경로가 안 잡히면 같은 폴더에서 NFC 대조로 진짜 경로를 찾아 출력 (읽기 전용)
  sweep <dir>      : 폴더 하위 NFD 이름을 NFC로 리네임. 기본 드라이런, --apply 시에만 실제 변경
"""
import os
import sys
import unicodedata


def _nfc(s):
    return unicodedata.normalize("NFC", s)


def resolve(path):
    """존재하면 그대로, 아니면 부모 폴더에서 NFC가 같은 실존 항목을 찾아 반환."""
    if os.path.exists(path):
        print(path)
        return 0
    parent = os.path.dirname(path) or "."
    target = _nfc(os.path.basename(path))
    if not os.path.isdir(parent):
        # 부모 폴더 자체가 NFD 차이일 수 있음 → 한 단계 위에서 부모부터 해소
        gp = os.path.dirname(parent) or "."
        pname = _nfc(os.path.basename(parent))
        if os.path.isdir(gp):
            for e in os.listdir(gp):
                if _nfc(e) == pname:
                    parent = os.path.join(gp, e)
                    break
    if os.path.isdir(parent):
        for e in os.listdir(parent):
            if _nfc(e) == target:
                found = os.path.join(parent, e)
                print(found)
                return 0
    sys.stderr.write("NOT_FOUND: %s\n" % path)
    return 1


def sweep(root, apply=False):
    """root 하위에서 NFD 이름만 NFC로 리네임. 깊은 곳부터(자식 먼저) 처리."""
    if not os.path.isdir(root):
        sys.stderr.write("NOT_A_DIR: %s\n" % root)
        return 1
    hits = []
    for dirpath, dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames + dirnames:
            nfc = _nfc(name)
            if nfc != name:
                hits.append((os.path.join(dirpath, name), os.path.join(dirpath, nfc)))
    if not hits:
        print("정규화 필요 항목 없음 (NFD 0개)")
        return 0
    print("NFD -> NFC 대상 %d개:" % len(hits))
    for src, dst in hits:
        print("  %s  ->  %s" % (os.path.basename(src), os.path.basename(dst)))
    if not apply:
        print("\n[드라이런] 실제 변경하려면 --apply 추가")
        return 0
    renamed = 0
    for src, dst in hits:
        if os.path.exists(dst):
            sys.stderr.write("SKIP(이미 존재): %s\n" % dst)
            continue
        os.rename(src, dst)
        renamed += 1
    print("\n적용 완료: %d개 리네임" % renamed)
    return 0


def main(argv):
    if len(argv) < 3:
        sys.stderr.write(__doc__)
        return 2
    cmd, arg = argv[1], argv[2]
    if cmd == "resolve":
        return resolve(arg)
    if cmd == "sweep":
        return sweep(arg, apply=("--apply" in argv[3:]))
    sys.stderr.write("unknown command: %s\n" % cmd)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
