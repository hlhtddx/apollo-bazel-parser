import logging
import sys
from pathlib import Path

logger = logging.getLogger('ABP')
logger.setLevel(logging.DEBUG)

from bazel.cc import gen_android_bp_files
from bazel.parse import parse_cquery_result
from proto.analysis_pb2 import CqueryResult


def main(argv):
    message = CqueryResult()

    if len(argv) > 1:
        with open(argv[1], 'rb') as f:
            data = f.read()
    else:
        data = sys.stdin.buffer.read()
    message.ParseFromString(data)
    parse_cquery_result(message)
    gen_android_bp_files(Path.cwd())
    print('done')


if __name__ == '__main__':
    main(sys.argv)
