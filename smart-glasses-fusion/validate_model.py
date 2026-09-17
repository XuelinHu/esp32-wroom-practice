import FreeCAD as App
import Part
from pathlib import Path


root = Path(__file__).resolve().parent
doc = App.openDocument(str(root / "output" / "smart_glasses_v1.FCStd"))
invalid = []
rows = []
for obj in doc.Objects:
    if not hasattr(obj, "Shape") or obj.Shape.isNull():
        continue
    box = obj.Shape.BoundBox
    valid = obj.Shape.isValid()
    if not valid:
        invalid.append(obj.Name)
    rows.append((obj.Name, valid, len(obj.Shape.Solids), box.XLength, box.YLength, box.ZLength))

for row in rows:
    print(f"{row[0]} valid={row[1]} solids={row[2]} bbox={row[3]:.2f}x{row[4]:.2f}x{row[5]:.2f}")
print(f"objects={len(rows)} invalid={len(invalid)}")
if invalid:
    raise SystemExit("Invalid shapes: " + ", ".join(invalid))
