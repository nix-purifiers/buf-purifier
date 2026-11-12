# SPDX-License-Identifier: MIT
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


spec = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2]); out.mkdir()
results = []
for index, case in enumerate(spec['cases']):
    generated, repository = Path(case['generated']), Path(case['repository'])
    model = json.loads((generated/'rust-products.json').read_text())
    catalog = json.loads((repository/'.catalog').read_text())
    entries = {p['name']:p for p in catalog['packages']}
    for name, expected in model['generatedHashes'].items():
        assert digest(generated/'crate'/name)==expected
    assert digest(generated/'descriptor.binpb')==model['descriptorSha256']
    project = Path('consumer-'+str(index))
    subprocess.run(['cargo','init','--bin','--name','consumer_'+str(index),'--edition','2021','--vcs','none',str(project)],check=True)
    (project/'.cargo').mkdir()
    (project/'.cargo/config.toml').write_text('[source.crates-io]\nreplace-with="provided"\n[source.provided]\nlocal-registry='+json.dumps(str(repository))+'\n')
    subprocess.run(['cargo','add','--offline',*[name+'@='+entries[name]['version'] for name in ['proof_schemas','prost']]],cwd=project,check=True)
    shutil.copy(Path(__file__).with_name('consumer.rs'),project/'src/main.rs')
    with (out/f'build-{index}.jsonl').open('w') as log:
        subprocess.run(['cargo','build','--offline','--locked','--message-format=json'],cwd=project,stdout=log,check=True)
    result = subprocess.check_output([str(project/'target/debug'/('consumer_'+str(index)))],text=True).strip()
    expected = ['42:43:0a02082a1202082b','42:43:0a02102a1202082b'][index]
    assert result==expected,(result,expected)
    metadata=json.loads(subprocess.check_output(['cargo','metadata','--offline','--locked','--format-version=1'],cwd=project,text=True))
    owned=next(p for p in metadata['packages'] if p['name']=='proof_schemas')
    runtime=next(p for p in metadata['packages'] if p['name']=='prost')
    compiled=Path(owned['manifest_path']).parent
    depfiles=list((project/'target/debug/deps').glob('proof_schemas-*.d'))
    assert depfiles
    dependencies='\n'.join(p.read_text() for p in depfiles)
    for name,sha in model['generatedHashes'].items():
        assert digest(compiled/name)==sha
        assert str(compiled/name) in dependencies
    sdk_source=Path(model['sdkRuntime']['prost']['manifest']).parent/'src/lib.rs'
    assert (Path(runtime['manifest_path']).parent/'src/lib.rs').read_bytes()==sdk_source.read_bytes()
    # The native Cargo archives, not a reconstructed manifest, are consumed.
    for name in ['proof_schemas','prost']:
        entry=entries[name];archive=repository/entry['archive']
        assert digest(archive)==entry['checksum']
        with tarfile.open(archive) as tar:
            members=[m for m in tar if m.name.endswith('/src/lib.rs')]
            assert len(members)==1
            original=generated/'crate/src/lib.rs' if name=='proof_schemas' else sdk_source
            assert tar.extractfile(members[0]).read()==original.read_bytes()
    shutil.copy(project/'Cargo.lock',out/f'Cargo-{index}.lock')
    (out/f'metadata-{index}.json').write_text(json.dumps(metadata,indent=2)+'\n')
    (out/f'dependencies-{index}.txt').write_text(dependencies)
    results.append({'output':result,'generated':str(generated),'repository':str(repository),'ownedManifest':owned['manifest_path'],'sdkManifest':runtime['manifest_path'],'model':model})
assert results[0]['model']['generatedHashes']!=results[1]['model']['generatedHashes']
# Native compiler controls use private copies, never fixture attestations.
from importlib.util import spec_from_file_location, module_from_spec
loader=spec_from_file_location('generator',spec['generator']);generator=module_from_spec(loader);loader.loader.exec_module(generator)
base=spec['cases'][0];config=json.loads(Path(base['rustSpec']).read_text())
def copy_producer(name):
    root=Path(name);(root/'schemas').mkdir(parents=True)
    shutil.copytree(Path(base['producer'])/'schemas',root/'schemas',dirs_exist_ok=True)
    for p in root.rglob('*'):
        if p.is_dir():p.chmod(0o755)
        elif not p.is_symlink():p.chmod(0o644)
    return root
missing=copy_producer('missing-import')
(missing/'schemas/purifier/proof/v1/common.proto').unlink()
try:
    generator.generate(missing.resolve(),Path('unexpected-missing').resolve(),dict(config,entrypoints=['purifier/proof/v1/answer.proto']))
except subprocess.CalledProcessError:
    pass
else:raise AssertionError('accepted missing captured schema')
shadow=copy_producer('sdk-shadow')
path=shadow/'schemas/google/protobuf/timestamp.proto';path.parent.mkdir(parents=True,exist_ok=True)
path.write_bytes((Path(config['include'])/'google/protobuf/timestamp.proto').read_bytes()+b'// incompatible SDK shadow\n')
try:
    generator.generate(shadow.resolve(),Path('unexpected-shadow').resolve(),config)
except ValueError as error:
    assert 'shadows a different SDK schema' in str(error)
else:raise AssertionError('accepted incompatible SDK schema shadow')
bad=Path('bad-registry');shutil.copytree(base['repository'],bad)
for p in bad.rglob('*'):
    if p.is_dir():p.chmod(0o755)
    elif not p.is_symlink():p.chmod(p.stat().st_mode|0o200)
cat=json.loads((bad/'.catalog').read_text());packages={p['name']:p for p in cat['packages']}
index=bad/'index/pr/os/prost';rows=[json.loads(line) for line in index.read_text().splitlines()]
for row in rows:
    if row['vers']==packages['prost']['version']:row['cksum']='0'*64
index.write_text(''.join(json.dumps(row)+'\n' for row in rows))
consumer=Path('bad-consumer');subprocess.run(['cargo','init','--bin','--name','bad_consumer','--edition','2021','--vcs','none',str(consumer)],check=True)
(consumer/'.cargo').mkdir();(consumer/'.cargo/config.toml').write_text('[source.crates-io]\nreplace-with="provided"\n[source.provided]\nlocal-registry='+json.dumps(str(bad.resolve()))+'\n')
import os
env=dict(os.environ,CARGO_HOME=str(Path('bad-cargo-home').resolve()))
subprocess.run(['cargo','add','--offline',*['%s@=%s'%(name,packages[name]['version']) for name in ['proof_schemas','prost']]],cwd=consumer,env=env,check=True)
shutil.copy(Path(__file__).with_name('consumer.rs'),consumer/'src/main.rs')
failed=subprocess.run(['cargo','build','--offline','--locked'],cwd=consumer,env=env,capture_output=True,text=True)
(out/'checksum-rejection.stderr').write_text(failed.stderr)
assert failed.returncode!=0 and 'checksum' in failed.stderr.lower() and 'prost' in failed.stderr.lower(),failed.stderr
(out/'verification.json').write_text(json.dumps({'consumers':results,'missingSchemaRejected':True,'sdkShadowRejected':True,'runtimeChecksumRejected':True},indent=2)+'\n')
