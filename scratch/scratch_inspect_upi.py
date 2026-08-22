import dbf
import os

path_01 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct01.dbf"
path_41 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct41.dbf"
path_40 = "/Users/jaydevnakum/Work Place/STOCK MARKET /APP DETAILS/Mirracle Auto Entre Sale or Purchase or Bank/CMP0006/YR26/rkacct40.dbf"

t01 = dbf.Table(path_01)
t41 = dbf.Table(path_41)
t40 = dbf.Table(path_40)

t01.open()
t41.open()
t40.open()

target_vid = None
for r in t01:
    if not dbf.is_deleted(r) and str(r['FIELD02']).strip() == '2026-06-19' and abs(r['FIELD05'] - 3100.0) < 0.1:
        target_vid = str(r['FIELD01']).strip()
        print(f"Found in T01: VID {target_vid}, Amount {r['FIELD05']}, Party {r['FIELD04']}")
        break

if target_vid:
    for r in t41:
        if not dbf.is_deleted(r) and str(r['FIELD01']).strip() == target_vid:
            print(f"T41 FIELD82 Narration: {repr(r['FIELD82'])}")
            break

    for r in t40:
        if not dbf.is_deleted(r) and str(r['T40F01']).strip() == target_vid:
            print(f"T40 T40F02 Narration: {repr(r['T40F02'])}")
            print(f"T40 T40F09 Type: {repr(r['T40F09'])}")

t01.close()
t41.close()
t40.close()
