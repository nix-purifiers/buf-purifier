# SPDX-License-Identifier: MIT
import json,os,shutil,subprocess,sys
from pathlib import Path
spec=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);out.mkdir()
rows=[]
for index,case in enumerate(spec):
 root=Path.cwd()/str(index);root.mkdir()
 env=dict(os.environ,HOME=str(root/'home'),GOPATH=str(root/'go'),GOCACHE=str(root/'cache'),GOMODCACHE=str(root/'modcache'),GOTOOLCHAIN='local',GOWORK='off',GOSUMDB='off',GOPROXY='file://'+case['repository']+',off')
 Path(env['HOME']).mkdir();shutil.copyfile(Path(__file__).parent/'consumer.go',root/'main.go')
 catalog=json.loads((Path(case['repository'])/'.catalog').read_text())
 versions={m['path']:m['version'] for m in catalog['modules']}
 assert set(versions)=={'example.org/proof','google.golang.org/protobuf'}
 def run(args,**kwargs):return subprocess.run(args,cwd=root,env=env,check=True,text=True,**kwargs)
 run(['go','mod','init','example.org/consumer'])
 run(['go','get','example.org/proof/purifier/proof/v1@'+versions['example.org/proof']])
 run(['go','build','-o',str(root/'consumer'),'.'])
 result=run([str(root/'consumer'),str(root/'runtime-source.txt'),str(case['field'])],capture_output=True).stdout.strip()
 values=result.split(':');assert values[:3]==['42','43',str(case['field'])]
 origins=json.loads((root/'runtime-source.txt').read_text());source=Path(origins['runtime'])
 expected_root=Path(env['GOMODCACHE'])/('google.golang.org/protobuf@'+versions['google.golang.org/protobuf'])
 assert source.is_relative_to(expected_root)
 relative=source.relative_to(expected_root)
 assert source.read_bytes()==(Path(case['runtimeSource'])/relative).read_bytes()
 owned=Path(origins['owned']);owned_root=Path(env['GOMODCACHE'])/('example.org/proof@'+versions['example.org/proof'])
 assert owned.is_relative_to(owned_root)
 owned_relative=owned.relative_to(owned_root)
 assert owned.read_bytes()==(Path(case['generated'])/owned_relative).read_bytes()
 (out/f'{index}-go.sum').write_bytes((root/'go.sum').read_bytes())
 info=run(['go','version','-m',str(root/'consumer')],capture_output=True).stdout
 assert all(v in info for v in versions.values());(out/f'{index}-build-info.txt').write_text(info)
 rows.append({'field':case['field'],'output':result,'modules':versions,'runtimeSource':str(relative),'runtimeSourceBytesMatch':True,'ownedSource':str(owned_relative),'ownedSourceBytesMatch':True})
assert rows[0]['output']!=rows[1]['output']
assert rows[0]['modules']['example.org/proof']!=rows[1]['modules']['example.org/proof']
assert rows[0]['modules']['google.golang.org/protobuf']==rows[1]['modules']['google.golang.org/protobuf']
(out/'proof.json').write_text(json.dumps(rows,indent=2)+'\n')
