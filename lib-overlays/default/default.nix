final: prev: {
  buf-purifier = {
    readLock = import ./read-lock.nix { lib = final; };
  };
}
