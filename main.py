import sys

from proto.analysis_pb2 import CqueryResult
from bazel.cc import gen_android_bp_files
from bazel.parse import parse_cquery_result


def main(argv):
    message = CqueryResult()

    if len(argv) > 1:
        with open(argv[1], 'rb') as f:
            data = f.read()
    else:
        data = sys.stdin.buffer.read()
    message.ParseFromString(data)
    parse_cquery_result(message)
    gen_android_bp_files('.')
    print('done')


if __name__ == '__main__':
    main(sys.argv)
