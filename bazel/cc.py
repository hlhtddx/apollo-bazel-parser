import logging
import re
from pathlib import Path
from typing import Set, Dict, List

from bazel import get_attr_boolean_value, get_attr_string_value, get_attr_string_list_value
from bazel import normalize_location, normalize_name

logger = logging.getLogger('ABP')


class CcModule(object):
    def __init__(self, name: str, rule_class: str, location: str or None, attributes: dict or None,
                 normal_name: str or None = None):
        self.name = name
        if normal_name:
            self.normal_name = normal_name
        else:
            self.normal_name = normalize_name(name)
        if location:
            self.path = normalize_location(location)
        else:
            self.path = None
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
            logger.debug(self)

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
        normal_srcs = []
        if self.srcs:
            for i in self.srcs:
                src_name = self._normalize_src_path(i)
                if src_name.endswith('.c') or src_name.endswith('.cc') or src_name.endswith('.cxx'):
                    normal_srcs.append(src_name)
            self.normal_srcs = normal_srcs

        # alternate rule_class for android
        if self.rule_class == 'cc_binary' and self.linkshared == True:
            self.rule_class = 'cc_library_shared'
        elif self.rule_class == 'cc_library':
            if not self.srcs:  # No source file defined, maybe a phony module
                if self.hdrs:
                    self.rule_class = 'cc_library_headers'
                elif not self.deps:
                    self.rule_class = 'cc_defaults'
            elif self.linkshared:
                self.rule_class = 'cc_library_shared'
            else:
                self.rule_class = 'cc_library_static'
        elif self.rule_class in ('cc_proto_library', 'proto_library'):
            self.rule_class = 'cc_library'

    SRC_PATTERN = re.compile(r'/(/(\w+))+:(.+)')

    def post_parse_process(self):
        for dep in self.deps:
            if dep not in cc_rules_by_name:
                # TODO add thirdparty library support
                logger.error('Cannot find deps %s', dep)
                continue
            module = cc_rules_by_name[dep]
            if module.rule_class == 'cc_library_shared':
                logger.debug('Add cc_library_shared %s for %s', self.name, module.name)
                self.shared_libs.append(module)
            elif module.rule_class == 'cc_library_static':
                logger.debug('Add cc_library_static %s for %s', self.name, module.name)
                self.static_libs.append(module)
            elif module.rule_class == 'cc_library_headers':
                logger.debug('Add cc_library_headers %s for %s', self.name, module.name)
                self.header_libs.append(module)
            elif module.rule_class == 'cc_defaults':
                logger.debug('Add cc_defaults %s for %s', self.name, module.name)
                self.defaults.append(module)
            else:
                logger.debug('Add required %s for %s', self.name, module.name)
                self.required.append(module)

    def output_to_android_bp(self, bp_file):
        # Skip BUILD outside
        if not self.path:
            return
        if self.rule_class == 'cc_library_headers':
            return

        bp_file.write(f'\n{self.rule_class} {{\n')
        # name
        bp_file.write(f'    /* bazel name: "{self.name}" */\n')
        bp_file.write(f'    name: "{self.normal_name}",\n')
        if self.rule_class in ('cc_binary', 'cc_library_shared'):
            bp_file.write(f'    vendor: true,\n')

        # output srcs
        if self.srcs:
            bp_file.write(f'    srcs: [\n')
            for i in self.normal_srcs:
                bp_file.write(f'        "{self.path}/{i}",\n')
            bp_file.write(f'    ],\n')

        output_dependencies(bp_file=bp_file, dependencies=self.shared_libs, label='shared_libs')
        output_dependencies(bp_file=bp_file, dependencies=self.static_libs, label='static_libs')
        output_dependencies(bp_file=bp_file, dependencies=self.defaults, label='defaults')
        output_dependencies(bp_file=bp_file, dependencies=self.required, label='required')
        output_dependencies(bp_file=bp_file, dependencies=self.includes, label='includes')

        if self.defines:
            pass

        bp_file.write('}\n')

    @staticmethod
    def _normalize_src_path(src_file_path: str):
        if src_file_path.startswith('//'):
            m = CcModule.SRC_PATTERN.match(src_file_path)
            return m[3]
        return src_file_path

    @staticmethod
    def _populate_lib_path(lib_path):
        return lib_path


cc_rules_by_name: Dict[str, CcModule] = {}


def output_dependencies(bp_file, dependencies: List[CcModule], label: str):
    if dependencies:
        bp_file.write(f'    {label}: [\n')
        for i in dependencies:
            bp_file.write(f'        /* {i.name} */\n')
            bp_file.write(f'        "{i.normal_name}",\n')
        bp_file.write(f'    ],\n')


def gen_android_bp_files(base_dir: Path):
    bp_file_path = Path.joinpath(base_dir, 'Android.bp')
    with open(bp_file_path, mode='w+') as bp_file:
        bp_file.write('/* Auto-generated by bazel BUILD file */\n')
        for module in cc_rules_by_name.values():
            if not module.path:
                continue
            module.output_to_android_bp(bp_file)


def parse_cc_rule(name, rule_class, location=None, attributes=None, normal_name=None):
    if name.startswith('@'):
        return
    module = CcModule(name, rule_class, location, attributes, normal_name)
    cc_rules_by_name[module.name] = module


def post_parse_cc_rules():
    for name, rule in cc_rules_by_name.items():
        rule.post_parse_process()


third_party_libs = {
    '@com_google_protobuf//:protobuf': 'libprotobuf-cpp-full',
    '@fastrtps//:fastrtps': 'fastrtps',
    '@fastcdr//:fastcdr': 'fastcdr',
    '@local_config_python//:python_headers': 'python_headers',
    '@local_config_python//:python_lib': 'python_lib',
    '@ncurses5//:ncurses5': 'ncurses5',
    '@com_github_google_glog//:glog': 'glog',
    '@com_github_gflags_gflags//:gflags': 'gflags',
    '@uuid//:uuid': 'uuid',
}

for bazel_name, android_name in third_party_libs.items():
    module = CcModule(bazel_name, 'cc_library_static', location=None, attributes=None, normal_name=android_name)
    cc_rules_by_name[bazel_name] = module
