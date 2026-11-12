# SPDX-License-Identifier: MIT
import json,os,subprocess,sys,tempfile
from pathlib import Path
helper,producer,protoc,include,plugin,go,runtime,destination=sys.argv[1:]
rows=[]
with tempfile.TemporaryDirectory() as temp:
 root=Path(temp)
 for name,module,entries,diagnostic in [
  ('wrong-native-module-prefix','example.org/other',['purifier/proof/v1/answer.proto'],'does not match prefix'),
  ('missing-exported-entrypoint','example.org/proof',['missing.proto'],'No such file'),
 ]:
  spec=root/(name+'.json');spec.write_text(json.dumps({'modulePath':module,'entrypoints':entries}))
  result=subprocess.run([sys.executable,helper,producer,str(root/name),str(spec),protoc,include,plugin,go,runtime],capture_output=True,text=True)
  assert result.returncode!=0 and diagnostic in result.stderr,(name,result.stderr)
  rows.append({'case':name,'exitCode':result.returncode,'expectedDiagnostic':diagnostic})
Path(destination).write_text(json.dumps(rows,indent=2)+'\n')
