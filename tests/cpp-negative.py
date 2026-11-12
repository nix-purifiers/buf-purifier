# SPDX-License-Identifier: MIT
"""Reject corrupted copies of a real exported native schema closure."""
import json,shutil,subprocess,sys,tempfile
from pathlib import Path
helper,package,protoc,include,compiler,suffix,destination=sys.argv[1:]
model=json.loads((Path(package)/'cpp-products.json').read_text())
producer=Path(model['producer']);rows=[]
with tempfile.TemporaryDirectory() as temporary:
 root=Path(temporary);bad=root/'input'
 shutil.copytree(producer/'schemas',bad/'schemas')
 for path in [bad,*bad.rglob('*')]:path.chmod(0o755 if path.is_dir() else 0o644)
 sdk=bad/'schemas/google/protobuf/timestamp.proto';sdk.parent.mkdir(parents=True,exist_ok=True);original=(Path(include)/'google/protobuf/timestamp.proto').read_bytes()
 sdk.write_bytes(original+b'\n// Controlled SDK schema mismatch\n')
 def reject(name,diagnostic):
  result=subprocess.run([sys.executable,helper,str(bad),str(root/name),protoc,include,'proof','0.1.0',compiler,suffix],capture_output=True,text=True)
  assert result.returncode!=0 and diagnostic in result.stderr,(name,result.stdout,result.stderr)
  rows.append({'case':name,'exitCode':result.returncode,'expectedDiagnostic':diagnostic})
 reject('sdk-schema-mismatch','captured schema conflicts with selected SDK')
 sdk.unlink()
 (bad/'schemas/purifier/proof/v1/common.proto').unlink()
 reject('missing-captured-import','purifier/proof/v1/common.proto')
Path(destination).write_text(json.dumps(rows,indent=2)+'\n')
