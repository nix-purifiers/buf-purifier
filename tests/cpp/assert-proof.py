# SPDX-License-Identifier: MIT
"""Require complete evidence and the expected native semantic observations."""
import json,sys
from pathlib import Path
root=Path(sys.argv[1])
required={'pkgconfig.txt','cmake.txt','schema1.txt','schema2.txt','schema1.json','schema2.json','negative.json'}
assert required.issubset({p.name for p in root.iterdir()})
assert (root/'pkgconfig.txt').read_text()==(root/'cmake.txt').read_text()=='42:7\n'
a,b=[(root/f'schema{n}.txt').read_text().strip().split(':') for n in (1,2)]
assert a[0]=='1' and b[0]=='2' and a[1]!=b[1]
models=[json.loads((root/f'schema{n}.json').read_text()) for n in (1,2)]
assert models[0]['version']==models[1]['version']=='0.1.0'
assert models[0]['librarySha256']!=models[1]['librarySha256']
for m in models:
 assert any(s['owner']=='sdk' and s['path']=='google/protobuf/timestamp.proto' for s in m['schemas'])
 assert not any(s['path'].startswith('google/protobuf/') for s in m['generated'])
controls=json.loads((root/'negative.json').read_text())
assert {c['case'] for c in controls}=={'sdk-schema-mismatch','missing-captured-import'}
assert all(c['exitCode']!=0 for c in controls)
(root/'verification.json').write_text(json.dumps({'allExpectedProofFilesPresent':True,'schemaFieldNumbers':[1,2],'samePackageVersionDistinctLibraries':True,'twoNegativeControlsRejected':True},indent=2)+'\n')
