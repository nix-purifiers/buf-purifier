# SPDX-License-Identifier: MIT
"""Use the native Go plugin and Go manifest editor without guessing imports."""
import hashlib,json,subprocess,sys
from pathlib import Path
producer,out,spec,protoc,include,plugin,go,runtime_source=sys.argv[1:]
producer,out=Path(producer),Path(out)
model=json.loads(Path(spec).read_text());schemas=(producer/'schemas').resolve()
for entry in model['entrypoints']:
 path=(schemas/entry).resolve(strict=True)
 if not path.is_relative_to(schemas) or not path.is_file():raise ValueError('Go entrypoint is outside exported schemas')
module=out/'module';module.mkdir(parents=True)
command=[protoc,'-I'+str(schemas),'-I'+include,'--plugin=protoc-gen-go='+plugin,'--descriptor_set_out='+str(out/'descriptor.binpb'),'--include_imports','--go_out='+str(module),'--go_opt=module='+model['modulePath'],*model['entrypoints']]
subprocess.run(command,cwd=schemas,check=True)
files=list(module.rglob('*.go'))
if not files:raise ValueError('native Go plugin produced no module sources')
sdk=json.loads(subprocess.check_output([go,'mod','edit','-json',str(Path(runtime_source)/'go.mod')],text=True))
if sdk['Module']['Path']!='google.golang.org/protobuf':raise ValueError('Go plugin runtime source is not the native protobuf module')
version=subprocess.check_output([plugin,'--version'],text=True).strip()
if not version.startswith('protoc-gen-go v'):raise ValueError('native Go plugin version is not identifiable')
subprocess.run([go,'mod','init',model['modulePath']],cwd=module,check=True)
subprocess.run([go,'mod','edit','-go='+sdk['Go'],'-require='+sdk['Module']['Path']+'@'+version.split()[-1]],cwd=module,check=True)
record={'producer':str(producer),'descriptorSha256':hashlib.sha256((out/'descriptor.binpb').read_bytes()).hexdigest(),'modulePath':model['modulePath'],'entrypoints':model['entrypoints'],'generatorVersion':version,'runtimeModule':sdk['Module']['Path'],'runtimeGoVersion':sdk['Go'],'command':command,'generated':[{'path':str(p.relative_to(module)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(files)]}
(out/'go-products.json').write_text(json.dumps(record,sort_keys=True,indent=2)+'\n')
