import dbf

def main():
    t41_path = "/Volumes/mirracle/CMP0006/YR26/RKACCT41.DBF"
    t41 = dbf.Table(t41_path)
    t41.open()
    print("--- ALL CONTRA (BC) VOUCHERS IN RKACCT41 ---")
    for r in t41:
        f98 = str(r['FIELD98']).strip()
        if f98 == 'BC':
            print(f"T41: ID={r['FIELD01']}, Date={r['FIELD02']}, Party={r['FIELD04']}, Bank={r['FIELD05']}, Amount={r['FIELD06']}, ChqNo={r['FIELD10']}, VouNo={r['FIELD12']}, F16={r['FIELD16']}, F21={r['FIELD21']}")
    t41.close()

if __name__ == "__main__":
    main()
