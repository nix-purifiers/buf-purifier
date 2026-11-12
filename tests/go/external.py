# SPDX-License-Identifier: MIT
import json,os,shutil,subprocess,sys
from pathlib import Path
spec=json.loads(Path(sys.argv[1]).read_text());out=Path(sys.argv[2]);out.mkdir()
root=Path.cwd()/'project';root.mkdir();env=dict(os.environ,HOME=str(root/'home'),GOPATH=str(root/'go'),GOCACHE=str(root/'cache'),GOMODCACHE=str(root/'modcache'),GOTOOLCHAIN='local',GOWORK='off',GOSUMDB='off',GOPROXY='file://'+spec['repository']+',off')
Path(env['HOME']).mkdir();shutil.copyfile(Path(__file__).parent/'external.go',root/'main.go')
versions={m['path']:m['version'] for m in json.loads((Path(spec['repository'])/'.catalog').read_text())['modules']}
assert set(versions)=={'example.org/proof','example.org/foreign','google.golang.org/protobuf'}
def run(args,**kw):return subprocess.run(args,cwd=root,env=env,check=True,text=True,**kw)
run(['go','mod','init','example.org/consumer'])
run(['go','get','example.org/proof/purifier/proof/v1@'+versions['example.org/proof']])
run(['go','build','-o',str(out/'consumer'),'.'])
result=run([str(out/'consumer'),str(root/'foreign-source.txt')],capture_output=True).stdout.strip();assert result=='77:1a02084d'
origin=Path((root/'foreign-source.txt').read_text());base=Path(env['GOMODCACHE'])/('example.org/foreign@'+versions['example.org/foreign']);assert origin.is_relative_to(base)
relative=origin.relative_to(base);assert origin.read_bytes()==(Path(spec['foreignSource'])/relative).read_bytes()
foreign_repo=Path(spec['foreignRepository']);repository=Path(spec['repository'])
files=list((foreign_repo/'example.org/foreign/@v').iterdir());assert files
for file in files:assert file.read_bytes()==(repository/file.relative_to(foreign_repo)).read_bytes()
(out/'go.sum').write_bytes((root/'go.sum').read_bytes());(out/'go.mod').write_bytes((root/'go.mod').read_bytes())
(out/'proof.json').write_text(json.dumps({'output':result,'modules':versions,'foreignSourceBytesMatch':True,'providedProxyFilesPreserved':len(files)},indent=2)+'\n')
