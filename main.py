import json
import logging
import sys
from pathlib import Path

from bazel.parse import Modules

logger = logging.getLogger('apollo')
logger.setLevel(logging.DEBUG)


def main(argv):
    if len(argv) > 1:
        with open(argv[1], 'r') as f:
            data = f.read()
    else:
        data = sys.stdin.read()
    message = json.loads(data)

    modules = Modules()
    modules.load_cquery_result(message)
    modules.gen_android_bp_files(Path.cwd())


if __name__ == '__main__':
    main(sys.argv)
