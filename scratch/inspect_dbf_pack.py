import dbf
import inspect

print("pack docstring:")
print(inspect.getdoc(dbf.Table.pack))

print("\npack signature:")
print(inspect.signature(dbf.Table.pack))
