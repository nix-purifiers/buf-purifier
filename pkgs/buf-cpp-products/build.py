# SPDX-License-Identifier: MIT
"""Generate and compile the captured schema closure with one Protobuf SDK."""
import hashlib,json,shlex,shutil,subprocess,sys,os,re
from pathlib import Path
producer,out,protoc,sdk_include,name,version,compiler,suffix=sys.argv[1:]
producer,out,sdk_include=Path(producer),Path(out),Path(sdk_include)
schemas=producer/'schemas';generated=out/'generated';generated.mkdir(parents=True)
sources=[];models=[]
for path in sorted(schemas.rglob('*.proto')):
 relative=path.relative_to(schemas);sdk=sdk_include/relative
 if sdk.is_file():
  if sdk.read_bytes()!=path.read_bytes():raise ValueError('captured schema conflicts with selected SDK: '+str(relative))
  owner='sdk'
 else:
  owner='captured-schema';sources.append(str(relative))
 models.append({'path':str(relative),'owner':owner,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
if not sources:raise ValueError('no non-SDK schemas to compile')
# Native Make dependency output includes SDK imports which buf export omits.
observed={(m['owner'],m['path']):m for m in models}
for source in sources:
 dependency=out/'native-dependencies'/Path(source).with_suffix('.d')
 dependency.parent.mkdir(parents=True,exist_ok=True)
 subprocess.run([protoc,'-I'+str(schemas),'-I'+str(sdk_include),'--cpp_out='+str(generated),'--dependency_out='+str(dependency),source],cwd=schemas,check=True)
 raw=dependency.read_text().replace('\\\n',' ')
 for entry in shlex.split(raw.split(':',1)[1]):
  path=Path(entry)
  if not path.is_absolute():
   path=next((base/path for base in (schemas,sdk_include) if (base/path).is_file()),None)
   if path is None:raise ValueError('native compiler input is missing: '+entry)
  if path.is_relative_to(schemas):
   relative=path.relative_to(schemas)
   if not path.resolve().is_relative_to(schemas.resolve()):raise ValueError('exported compiler input escapes schema root')
   sdk=sdk_include/relative
   owner='sdk' if sdk.is_file() else 'captured-schema'
   if sdk.is_file() and sdk.read_bytes()!=path.read_bytes():raise ValueError('captured schema conflicts with selected SDK: '+str(relative))
  elif path.is_relative_to(sdk_include):
   relative=path.relative_to(sdk_include);owner='sdk'
  else:raise ValueError('native compiler input has no declared owner: '+str(path))
  record={'path':str(relative),'owner':owner,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
  key=(owner,str(relative))
  if key in observed and observed[key]!=record:raise ValueError('native schema input changed during compilation')
  observed[key]=record
models=[observed[key] for key in sorted(observed)]
runtime_version=subprocess.check_output(['pkg-config','--modversion','protobuf'],text=True).strip()
lib=out/'lib';lib.mkdir();library=lib/('lib'+name+suffix)
work=Path(os.environ['TMPDIR'])/'cpp-build';work.mkdir()
cmake_sources='\n'.join('"'+str(p)+'"' for p in sorted(generated.rglob('*.pb.cc')))
(work/'CMakeLists.txt').write_text(f"""cmake_minimum_required(VERSION 3.20)
project(BufBindings LANGUAGES CXX)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_EXPORT_COMPILE_COMMANDS ON)
find_package(Protobuf CONFIG REQUIRED)
file(WRITE "${{CMAKE_BINARY_DIR}}/protobuf-version.txt" "${{Protobuf_VERSION}}")
add_library({name} SHARED {cmake_sources})
target_include_directories({name} PRIVATE "{generated}")
target_link_libraries({name} PRIVATE protobuf::libprotobuf)
install(TARGETS {name} LIBRARY DESTINATION lib)
include(CMakePackageConfigHelpers)
write_basic_package_version_file("{out}/lib/cmake/{name}/{name}ConfigVersion.cmake" VERSION "{version}" COMPATIBILITY ExactVersion)
""")
subprocess.run(['cmake','-S',str(work),'-B',str(work/'build'),'-DCMAKE_BUILD_TYPE=Release','-DCMAKE_INSTALL_PREFIX='+str(out),'-DCMAKE_CXX_COMPILER='+compiler],check=True)
subprocess.run(['cmake','--build',str(work/'build'),'--parallel','2'],check=True)
subprocess.run(['cmake','--install',str(work/'build')],check=True)
cmake_runtime_version=(work/'build/protobuf-version.txt').read_text()
commands=json.loads((work/'build/compile_commands.json').read_text())
standards={next((a for a in shlex.split(c['command']) if a.startswith('-std=')), '') for c in commands}
if len(standards)!=1:raise ValueError('native CMake compiler standard is ambiguous')
standard=standards.pop()
if not standard:
 macros=subprocess.check_output([compiler,'-dM','-E','-x','c++','-'],input='',text=True)
 value=int(re.search(r'^#define __cplusplus ([0-9]+)L',macros,re.M).group(1))
 if value<201103:raise ValueError('selected compiler default is older than C++11')
 standard='-std=c++'+str((value//100)%100)
match=re.fullmatch(r'-std=(?:gnu|c)\+\+([0-9]+)',standard)
if not match:raise ValueError('native compiler standard cannot be exported as a CMake feature')
cmake_feature='cxx_std_'+match.group(1)
shutil.copyfile(work/'build/compile_commands.json',out/'compile_commands.json')
for header in generated.rglob('*.pb.h'):
 target=out/'include'/header.relative_to(generated);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(header,target)
pc=lib/'pkgconfig';pc.mkdir();(pc/(name+'.pc')).write_text(f'prefix={out}\nlibdir=${{prefix}}/lib\nincludedir=${{prefix}}/include\n\nName: {name}\nDescription: Buf captured Protobuf C++ bindings\nVersion: {version}\nRequires: protobuf = {runtime_version}\nLibs: -L${{libdir}} -l{name}\nCflags: {standard} -I${{includedir}}\n')
config=lib/'cmake'/name;config.mkdir(parents=True,exist_ok=True)
(config/(name+'Config.cmake')).write_text(f'''include_guard(GLOBAL)
include(CMakeFindDependencyMacro)
find_dependency(Protobuf {cmake_runtime_version} EXACT CONFIG REQUIRED)
add_library({name}::{name} SHARED IMPORTED)
set_target_properties({name}::{name} PROPERTIES IMPORTED_LOCATION "{library}" INTERFACE_INCLUDE_DIRECTORIES "{out}/include" INTERFACE_LINK_LIBRARIES protobuf::libprotobuf INTERFACE_COMPILE_FEATURES {cmake_feature})
''')
model={'name':name,'version':version,'producer':str(producer),'librarySha256':hashlib.sha256(library.read_bytes()).hexdigest(),'abi':'c++','library':str(library.relative_to(out)),'compilerVersion':subprocess.check_output([protoc,'--version'],text=True).strip(),'runtimeVersion':runtime_version,'cmakeRuntimeVersion':cmake_runtime_version,'cxxStandard':standard,'schemas':models,'generated':[{'path':str(p.relative_to(generated)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sorted(generated.rglob('*')) if p.is_file()]}
(out/'cpp-products.json').write_text(json.dumps(model,sort_keys=True,indent=2)+'\n')
