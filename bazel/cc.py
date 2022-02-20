import re
from pathlib import Path
from typing import Set, List, Dict

from bazel import get_attr_boolean_value, get_attr_string_value, get_attr_string_list_value
from bazel import normalize_location, normalize_name


class CcModule(object):
    def __init__(self, name: str, rule_class: str, location: str, attributes: dict):
        self.name = normalize_name(name)
        self.path = normalize_location(location)
        self.rule_class = rule_class

        self.srcs = get_attr_string_list_value('srcs', attributes, [])
        self.deps = get_attr_string_list_value('deps', attributes, [])
        self.hdrs = get_attr_string_list_value('hdrs', attributes, [])

        self.copts = get_attr_string_list_value('copts', attributes, [])
        self.nocopts = get_attr_string_list_value('nocopts', attributes, [])

        self.defines = get_attr_string_list_value('defines', attributes, [])
        self.linkopts = get_attr_string_list_value('linkopts', attributes, [])
        self.local_defines = get_attr_string_list_value('local_defines', attributes, [])
        self.interface_library = get_attr_string_value('interface_library', attributes, None)
        self.includes = get_attr_string_list_value('includes', attributes, [])
        self.include_prefix = get_attr_string_value('include_prefix', attributes, None)
        self.strip_include_prefix = get_attr_string_value('strip_include_prefix', attributes, None)
        self.textual_hdrs = get_attr_string_list_value('textual_hdrs', attributes, [])

        self.linkshared = get_attr_boolean_value('linkshared', attributes, False)
        self.linkstatic = get_attr_boolean_value('linkstatic', attributes, True)

        self.alwayslink = get_attr_boolean_value('alwayslink', attributes, False)
        self.shared_library = get_attr_string_value('shared_library', attributes, None)
        self.static_library = get_attr_string_value('static_library', attributes, None)
        self.system_provided = get_attr_boolean_value('system_provided', attributes, False)

        self._post_init()
        self.shared_libs = []
        self.static_libs = []
        self.header_libs = []
        self.defaults = []
        self.required = []

        if self.path:
            print(self)

    def __str__(self):
        return '\n'.join([
            'name=' + self.name,
            '\tpath=' + str(self.path),
            '\tsrcs=' + str(self.srcs),
            '\tdeps=' + str(self.deps),
            '\tcopts=' + str(self.copts),
            '\tdefines=' + str(self.defines),
            '\tlinkopts=' + str(self.linkopts),
            '\tlinkshared=' + str(self.linkshared),
            '\tlinkstatic=' + str(self.linkstatic),
            '\tlocal_defines=' + str(self.local_defines),
            '\tnocopts=' + str(self.nocopts),
            '\thdrs=' + str(self.hdrs),
            '\talwayslink=' + str(self.alwayslink),
            '\tinterface_library=' + str(self.interface_library),
            '\tshared_library=' + str(self.shared_library),
            '\tstatic_library=' + str(self.static_library),
            '\tsystem_provided=' + str(self.system_provided)
        ])

    def _post_init(self):
        srcs = []
        for i in self.srcs:
            src_name = self._normalize_src_path(i)
            if src_name.endswith('.c') or src_name.endswith('.cc') or src_name.endswith('.cxx'):
                srcs.append(src_name)
        self.srcs = srcs

        # alternate rule_class for android
        if not self.srcs:  # No source file defined, maybe a phony module
            if self.hdrs:
                self.rule_class = 'cc_library_headers'
            else:
                self.rule_class = 'cc_defaults'
        elif self.rule_class == 'cc_library':
            if self.linkshared:
                self.rule_class = 'cc_library_shared'
            else:
                self.rule_class = 'cc_library_static'
        elif self.rule_class in ('cc_proto_library', 'proto_library'):
            self.rule_class = 'cc_library'

    SRC_PATTERN = re.compile(r'/(/(\w+))+:(.+)')

    @staticmethod
    def _normalize_src_path(src_file_path: str):
        if src_file_path.startswith('//'):
            m = CcModule.SRC_PATTERN.match(src_file_path)
            return m[3]
        return src_file_path

    @staticmethod
    def _populate_lib_path(lib_path):
        new_path = normalize_name(lib_path)

        # change protobuf to android cpp libname
        if new_path == 'protobuf':
            new_path = 'libproto-cpp-full'
        return new_path

    def output_to_android_bp(self, bp_file):
        # Skip BUILD outside
        if not self.path:
            return
        if self.rule_class == 'cc_library_headers':
            return

        bp_file.write(f'\n{self.rule_class} {{\n')
        bp_file.write(f'    name: "{self.name}",\n')
        bp_file.write(f'    vendor: true,\n')

        # output srcs
        if self.srcs:
            bp_file.write(f'    srcs: [\n')
            for i in self.srcs:
                bp_file.write(f'        "{self.path}/{self._normalize_src_path(i)}",\n')
            bp_file.write(f'    ],\n')

        # output libs
        if self.shared_libs:
            bp_file.write(f'    shared_libs: [\n')
            for i in self.shared_libs:
                bp_file.write(f'        "{self._populate_lib_path(i)}",\n')
            bp_file.write(f'    ],\n')

        if self.static_libs:
            bp_file.write(f'    static_libs: [\n')
            for i in self.static_libs:
                bp_file.write(f'        "{self._populate_lib_path(i)}",\n')
            bp_file.write(f'    ],\n')

        if self.defaults:
            bp_file.write(f'    defaults: [\n')
            for i in self.defaults:
                bp_file.write(f'        "{self._populate_lib_path(i)}",\n')
            bp_file.write(f'    ],\n')

        if self.required:
            bp_file.write(f'    required: [\n')
            for i in self.required:
                bp_file.write(f'        "{self._populate_lib_path(i)}",\n')
            bp_file.write(f'    ],\n')

        if self.includes:
            bp_file.write(f'    includes: [\n')
            for i in self.includes:
                bp_file.write(f'        "{i}",\n')
            bp_file.write(f'    ],\n')

        if self.defines:
            pass

        bp_file.write('}\n')

    def post_parse_process(self):
        for dep in self.deps:
            module = cc_rules_by_name[dep]
            if module.rule_class == 'cc_library_shared':
                self.shared_libs.append(module)
            elif module.rule_class == 'cc_library_static':
                self.static_libs.append(module)
            elif module.rule_class == 'cc_library_headers':
                self.header_libs.append(module)
            elif module.rule_class == 'cc_defaults':
                self.defaults.append(module)
            else:
                self.required.append(module)


cc_rules_by_name: Dict[str, CcModule] = {}
cc_rules_by_path: Dict[str, Set[CcModule]] = {}


def gen_android_bp_files(base_dir: str):
    bp_file_path = Path.joinpath(Path(base_dir), 'Android.bp')
    with open(bp_file_path, 'w') as bp_file:
        bp_file.write('/* Auto-generated by bazel BUILD file */\n')
        for filepath, modules in cc_rules_by_path.items():
            if not filepath:
                continue
            gen_android_bp_file(bp_file, modules)


def gen_android_bp_file(bp_file, modules: Set[CcModule]):
    for module in modules:
        module.output_to_android_bp(bp_file)


def parse_cc_rule(name, rule_class, location, attributes):
    module = CcModule(name, rule_class, location, attributes)
    cc_rules_by_name[module.name] = module
    if module.path not in cc_rules_by_path:
        cc_rules_by_path[module.path] = set()
    cc_rules_by_path[module.path].add(module)


def post_parse_cc_rules():
    for name, rule in cc_rules_by_name.items():
        rule.post_parse_process()
