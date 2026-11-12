#include "purifier/proof/v1/answer.pb.h"
#include <dlfcn.h>
#include <filesystem>
#include <iostream>
#include <iomanip>
int main(int argc,char**argv) {
  purifier::proof::v1::Answer source;
  source.mutable_common()->set_value(42);
  source.mutable_timestamp()->set_seconds(43);
  auto wire=source.SerializeAsString();
  purifier::proof::v1::Answer copy;
  if(!copy.ParseFromString(wire) || copy.common().value()!=42 || copy.timestamp().seconds()!=43) return 1;
  int field=purifier::proof::v1::Common::descriptor()->FindFieldByName("value")->number();
  if(field!=std::stoi(argv[3])) return 2;
  Dl_info owned{},sdk{};
  if(!dladdr(*reinterpret_cast<void**>(&copy),&owned) || !dladdr(*reinterpret_cast<void**>(source.mutable_timestamp()),&sdk)) return 3;
  if(std::filesystem::canonical(owned.dli_fname)!=std::filesystem::canonical(argv[1])) return 4;
  if(std::filesystem::canonical(sdk.dli_fname)!=std::filesystem::canonical(argv[2])) return 5;
  std::cout<<field<<":";
  for(unsigned char c:wire) std::cout<<std::hex<<std::setw(2)<<std::setfill('0')<<(int)c;
  std::cout<<"\n";
}
