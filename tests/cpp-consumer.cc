#include "proof/v1/proof.pb.h"
#include <google/protobuf/empty.pb.h>
#include <dlfcn.h>
#include <iostream>
#include <filesystem>
#include <stdexcept>
int main(int argc, char** argv) {
  proof::v1::Proof input;
  input.set_answer(42);
  input.mutable_fraction()->set_numerator(7);
  std::string wire=input.SerializeAsString();
  proof::v1::Proof output;
  if (!output.ParseFromString(wire) || output.answer()!=42 || output.fraction().numerator()!=7) return 1;
  Dl_info info{};
  if (!dladdr(*reinterpret_cast<void**>(&output), &info)) return 2;
  if (std::filesystem::canonical(info.dli_fname)!=std::filesystem::canonical(argv[1])) return 3;
  std::cout << output.answer() << ":" << output.fraction().numerator() << "\n";
}
