from pathlib import Path

file = Path("private/bufpkg/bufmodule/bufmodulecache/base_provider.go")
text = file.read_text()
text = text.replace('"context"', '"context"\n\t"fmt"\n\t"os"', 1)
needle = "\tdelegateValues, err := p.delegateGetValuesForKeys("
assert text.count(needle) == 1
text = text.replace(needle, '''\tif os.Getenv("BUF_PURIFIER_FROZEN") == "1" && len(notFoundKeys) > 0 {
        return nil, fmt.Errorf("buf-purifier: dependency is absent from the locked Nix cache; update the lock")
    }
''' + needle)
file.write_text(text)
