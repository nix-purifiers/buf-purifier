# SPDX-License-Identifier: MIT
"""Use native Prost/Cargo metadata, generation and manifest editing."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def generate(producer, output, model):
    schemas = (producer / 'schemas').resolve(strict=True)
    include = Path(model['include'])
    entries = model['entrypoints']
    for name in entries:
        path = (schemas / name).resolve(strict=True)
        if not path.is_relative_to(schemas) or not path.is_file():
            raise ValueError('Rust entrypoint is outside exported schemas')
    output.mkdir(parents=True)
    # Ask protoc for the actual imported source closure, including SDK files.
    dependency_rules, schema_hashes, sdk_hashes = {}, {}, {}
    for index, name in enumerate(entries):
        rule = output / ('dependency-' + str(index) + '.d')
        subprocess.run(['protoc', '-I' + str(schemas), '-I' + str(include),
                        '--descriptor_set_out=' + str(output / ('entry-' + str(index) + '.binpb')),
                        '--dependency_out=' + str(rule), name], cwd=schemas, check=True)
        dependency_rules[name] = rule.read_text()
        for value in shlex.split(rule.read_text().split(':', 1)[1].replace('\\\n', '')):
            path = Path(value)
            if not path.is_absolute():
                path = next((base / path for base in (schemas,include) if (base / path).is_file()),None)
                if path is None:
                    raise ValueError('native schema dependency is absent: ' + value)
            if path.is_relative_to(schemas):
                if not path.resolve(strict=True).is_relative_to(schemas):
                    raise ValueError('exported schema dependency escapes captured tree')
                relative = str(path.relative_to(schemas))
                sdk = include / relative
                if sdk.is_file() and digest(path) != digest(sdk):
                    raise ValueError('captured schema shadows a different SDK schema: ' + relative)
                schema_hashes[relative] = digest(path)
            elif path.is_relative_to(include):
                # Selected SDK schemas can themselves be symlinks to its proto
                # output. Retain their native logical include paths and bytes.
                sdk_hashes[str(path.relative_to(include))] = digest(path)
            else:
                raise ValueError('native schema dependency escapes captured tree and SDK: ' + str(path))
    sdk = Path('sdk-source')
    shutil.copytree(model['sdkSource'], sdk)
    sdk.chmod(0o755)
    for path in sdk.rglob('*'):
        if path.is_dir(): path.chmod(0o755)
        elif not path.is_symlink(): path.chmod(path.stat().st_mode | 0o200)
    (sdk / '.cargo').mkdir(exist_ok=True)
    config = (Path(model['vendor']) / '.cargo/config.toml').read_text()
    (sdk / '.cargo/config.toml').write_text(config)
    metadata = json.loads(subprocess.check_output(['cargo','metadata','--offline','--locked','--format-version=1'],cwd=sdk,text=True))
    packages = {p['id']:p for p in metadata['packages']}
    root = metadata['resolve']['root']
    node = next(n for n in metadata['resolve']['nodes'] if n['id']==root)
    runtime = {}
    for alias in ['prost','prost_types']:
        deps = [d for d in node['deps'] if d['name']==alias]
        if len(deps)!=1:
            raise ValueError('ambiguous native generator runtime dependency: ' + alias)
        package = packages[deps[0]['pkg']]
        runtime[package['name']] = {'version':package['version'],'manifest':package['manifest_path']}
    crate = output / 'crate'
    subprocess.run(['cargo','init','--lib','--name',model['name'],'--edition',packages[root]['edition'],
                    '--vcs','none',str(crate)],check=True)
    (crate / '.cargo').mkdir()
    (crate / '.cargo/config.toml').write_text(config)
    subprocess.run(['cargo','add','--offline',*[name+'@='+value['version'] for name,value in sorted(runtime.items())]],cwd=crate,check=True)
    command = ['protoc','-I'+str(schemas),'-I'+str(include),
               '--plugin=protoc-gen-prost='+model['prost']+'/bin/protoc-gen-prost',
               '--plugin=protoc-gen-prost-crate='+model['crateGenerator']+'/bin/protoc-gen-prost-crate',
               '--descriptor_set_out='+str(output/'descriptor.binpb'),'--include_imports',
               '--prost_out='+str(crate/'src'),'--prost-crate_out='+str(crate),
               '--prost-crate_opt=no_features,gen_crate='+str(crate/'Cargo.toml'),*entries]
    subprocess.run(command,cwd=schemas,check=True)
    # SDK preparation is for generation only; downstream resolution uses the
    # explicitly supplied native Cargo projector and its local registry.
    (crate/'.cargo/config.toml').unlink()
    (crate/'.cargo').rmdir()
    generated = {str(p.relative_to(crate)):digest(p) for p in sorted((crate/'src').rglob('*.rs'))}
    if not generated:
        raise ValueError('native Prost generator produced no Rust sources')
    (output/'rust-products.json').write_text(json.dumps({
        'producer':str(producer),'entrypoints':entries,'schemaHashes':schema_hashes,
        'sdkSchemaHashes':sdk_hashes,'nativeDependencies':dependency_rules,
        'descriptorSha256':digest(output/'descriptor.binpb'),'generatedHashes':generated,
        'nativeSdkRoot':root,'sdkRuntime':runtime,'command':command,
    },sort_keys=True,indent=2)+'\n')


if __name__ == '__main__':
    generate(Path(sys.argv[1]),Path(sys.argv[2]),json.loads(Path(sys.argv[3]).read_text()))
