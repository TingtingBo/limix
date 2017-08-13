from __future__ import division


def array_hash(X):
    writeable = X.flags.writeable
    X.flags.writeable = False
    h = hash(X.tobytes())
    X.flags.writeable = writeable
    return h