import dbf
import inspect

import dbf
print("dbf exports:")
for name in dir(dbf):
    if not name.startswith("_"):
        print(f" - {name}")

