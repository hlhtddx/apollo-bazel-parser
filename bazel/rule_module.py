import logging
import re
from pathlib import Path
from typing import List, Set

from bazel import get_attr_value, normalize_name
from .module import Module

logger = logging.getLogger('apollo')


class RuleModule(Module):
    @staticmethod
    def create_rule(message):
        rule = message["rule"]
        name = rule['name']
        location = rule['location']
        rule_class = rule["ruleClass"]
        attribute = rule['attribute']

        if name.startswith('@'):
            return None
        if rule_class in ('cc_binary', 'cc_library'):
            return CcModule(name, location, rule_class, attribute)
        elif rule_class in ('cc_proto_library', 'proto_library'):
            return ProtoCcModule(name, location, rule_class, attribute)
        return None

    def __init__(self, name: str, location: str, rule_class: str, attribute: List, normal_name: str):
        super().__init__(name, location, normal_name)
        self.rule_class = rule_class
        self.module_class = self.rule_class
        self.attributes = {}
        for attr in attribute:
            self.attributes[attr["name"]] = attr

        self.srcs = get_attr_value('srcs', self.attributes, 'stringListValue', [])
        self.deps = get_attr_value('deps', self.attributes, 'stringListValue', [])
        self.hdrs = get_attr_value('hdrs', self.attributes, 'stringListValue', [])

        self.copts = get_attr_value('copts', self.attributes, 'stringListValue', [])
        self.nocopts = get_attr_value('nocopts', self.attributes, 'stringListValue', [])

        self.defines = get_attr_value('defines', self.attributes, 'stringListValue', [])
        self.linkopts = get_attr_value('linkopts', self.attributes, 'stringListValue', [])
        self.local_defines = get_attr_value('local_defines', self.attributes, 'stringListValue', [])
        self.interface_library = get_attr_value('interface_library', self.attributes, 'stringValue')
        self.includes = get_attr_value('includes', self.attributes, 'stringListValue', [])
        self.include_prefix = get_attr_value('include_prefix', self.attributes, 'stringValue')
        self.strip_include_prefix = get_attr_value('strip_include_prefix', self.attributes, 'stringValue')
        self.textual_hdrs = get_attr_value('textual_hdrs', self.attributes, 'stringListValue', [])

        self.linkshared = get_attr_value('linkshared', self.attributes, 'booleanValue', False)
        self.linkstatic = get_attr_value('linkstatic', self.attributes, 'booleanValue', True)

        self.alwayslink = get_attr_value('alwayslink', self.attributes, 'booleanValue', False)
        self.shared_library = get_attr_value('shared_library', self.attributes, 'stringValue')
        self.static_library = get_attr_value('static_library', self.attributes, 'stringValue')
        self.system_provided = get_attr_value('system_provided', self.attributes, 'booleanValue', False)

    SRC_PATTERN = re.compile(r'/(/(\w+))+:(.+)')

    @staticmethod
    def _normalize_src_path(src_file_path: str):
        if src_file_path.startswith('//'):
            m = CcModule.SRC_PATTERN.match(src_file_path)
            return m[3]
        return src_file_path

    @staticmethod
    def _populate_lib_path(lib_path):
        return lib_path

    @staticmethod
    def output_items(bp_file, items: Set[str], label: str, filter_func=None):
        if items:
            bp_file.write(f'    {label}: [\n')
            for i in items:
                j = filter_func(i) if filter_func else i
                if not j:
                    continue
                bp_file.write(f'        "{j}",\n')
            bp_file.write(f'    ],\n')

    @staticmethod
    def output_modules(bp_file, items: Set[Module], label: str, filter_func=None):
        if items:
            bp_file.write(f'    {label}: [\n')
            for i in items:
                if filter_func and not filter_func(i):
                    continue
                # bp_file.write(f'        /* {i.name} */\n')
                bp_file.write(f'        "{i.normal_name}",\n')
            bp_file.write(f'    ],\n')


class CcModule(RuleModule):
    def __init__(self, name: str, location: str, rule_class: str, attribute: List, normal_name: str = ''):
        super().__init__(name, location, rule_class, attribute, normal_name)

        self.shared_libs = set()
        self.static_libs = set()
        self.header_libs = set()
        self.export_include_dirs = set()

    def post_load(self, modules):
        if self.rule_class == 'cc_binary':
            if self.linkshared:
                self.module_class = 'cc_library_shared'
            else:
                self.module_class = 'cc_binary'
        elif self.rule_class == 'cc_library':
            if not self.linkstatic or self.linkshared:
                self.module_class = 'cc_library_shared'
            else:
                self.module_class = 'cc_library_static'

        self.deps.append('@com_github_gflags_gflags//:gflags')
        self.deps.append('@com_github_google_glog//:glog')
        self.deps.append('@fastrtps//:fastrtps')
        self.deps.append('@fastcdr//:fastcdr')
        self.deps.append('libcyber-proto')
        # check header exports
        if self.hdrs:
            for hdr in self.hdrs:
                file_path = Path(self.path).joinpath(self._normalize_src_path(hdr))
                self.export_include_dirs.add(str(file_path.parent))
                logger.warning(f'{self.location} exports: {self.export_include_dirs}')

    def parse(self, modules):
        for dep in self.deps:
            if dep not in modules:
                # TODO add thirdparty library support
                logger.error('Cannot find deps %s', dep)
                continue
            module = modules[dep]
            if not isinstance(module, RuleModule):
                continue
            if module.module_class == 'cc_library_shared':
                logger.warning('Add cc_library_shared %s for %s', self.name, module.name)
                self.shared_libs.add(module)
            elif module.module_class == 'cc_library_static':
                logger.warning('Add cc_library_static %s for %s', self.name, module.name)
                self.static_libs.add(module)
            elif module.module_class == 'cc_library_headers':
                logger.warning('Add cc_library_headers %s for %s', self.name, module.name)
                self.header_libs.add(module)
            else:
                raise 2

    def output(self, bp_file):
        # Skip BUILD outside
        if not self.path:
            return

        bp_file.write(f'\n/* generated by {self.location} */\n')
        bp_file.write(f'{self.module_class} {{\n')
        # name
        # bp_file.write(f'    /* bazel name: "{self.name}" */\n')
        bp_file.write(f'    name: "{self.normal_name}",\n')
        #        if self.rule_class in ('cc_binary', 'cc_library_shared'):
        bp_file.write(f'    vendor: true,\n')
        bp_file.write(f'    rtti: true,\n')
        bp_file.write('''    cppflags: [
        "-fexceptions",
        "-Wno-non-virtual-dtor",
    ],\n''')

        def filter_source_file(item):
            src_name = self._normalize_src_path(item)
            if src_name.endswith('.c') or src_name.endswith('.cc') or src_name.endswith('.cxx'):
                return Path(self.path).joinpath(src_name)
            return None

        self.output_items(bp_file=bp_file, items=self.srcs, label='srcs', filter_func=filter_source_file)
        # self.output_items(bp_file=bp_file, items=self.export_include_dirs, label='export_include_dirs')

        self.output_modules(bp_file=bp_file, items=self.shared_libs, label='shared_libs')
        self.output_modules(bp_file=bp_file, items=self.static_libs, label='whole_static_libs')
        self.output_modules(bp_file=bp_file, items=self.header_libs, label='header_libs')

        if self.defines:
            raise 2

        bp_file.write('}\n')


class ProtoCcModule(CcModule):
    def __init__(self, name: str, location: str, rule_class: str, attribute: List, normal_name: str = ''):
        super().__init__(name, location, rule_class, attribute, normal_name)

    def post_load(self, modules):
        self.normal_name = self.path_to_module_name(self.path)
        self.module_class = 'cc_library_shared'
        if self.normal_name in modules:
            true_module = modules[self.normal_name]
        else:
            true_module = ProtoSharedModule(self.normal_name, self.location)
            modules[self.normal_name] = true_module
        true_module.merge(self)

    def parse(self, bp_file):
        pass

    def output(self, bp_file):
        pass

    @staticmethod
    def path_to_module_name(path_name: str):
        return 'lib' + path_name.replace('/', '-')


class ProtoSharedModule(RuleModule):
    def __init__(self, name: str, location: str):
        super().__init__(name, location, 'cc_library_shared', [], name)
        self.module_class = 'cc_library_shared'

    def post_load(self, modules):
        pass

    def parse(self, bp_file):
        pass

    def output(self, bp_file):
        bp_file.write(f'\n/* generated by {self.location} */\n')
        bp_file.write(f'{self.module_class} {{\n')
        bp_file.write(f'    name: "{self.normal_name}",\n')
        bp_file.write(f'    vendor: true,\n')
        bp_file.write('''    cppflags: [
        "-DGOOGLE_PROTOBUF_NO_RTTI",
        "-fexceptions",
        "-Wno-non-virtual-dtor",
    ],\n''')

        def filter_source_file(item):
            src_name = self._normalize_src_path(item)
            if src_name.endswith('.proto'):
                return Path(self.path).joinpath(src_name)
            return None

        self.output_items(bp_file=bp_file, items=self.srcs, label='srcs', filter_func=filter_source_file)
        bp_file.write('''    proto: {
        export_proto_headers: true,
		type: "full",
        canonical_path_from_root: false,
        local_include_dirs: [
            ".",
        ]
    }\n''')
        bp_file.write('}\n')

    def merge(self, module: ProtoCcModule):
        self.srcs += module.srcs
        logger.warning(f'merged: {self.srcs}')


class HeaderLibModule(RuleModule):
    def __init__(self, name: str, location: str):
        super().__init__(name, location, 'cc_library_static', [], name)
        self.module_class = 'cc_library_static'

    def post_load(self, modules):
        pass

    def parse(self, bp_file):
        pass

    def output(self, bp_file):
        bp_file.write(f'\n/* generated by {self.location} */\n')
        bp_file.write(f'{self.module_class} {{\n')
        bp_file.write(f'    name: "{self.normal_name}",\n')
        bp_file.write(f'    vendor: true,\n')
        bp_file.write(f'    export_include_dirs: [ "{self.path}" ]\n')
        bp_file.write('}\n')

    def merge(self, module: ProtoCcModule):
        self.srcs += module.srcs
        logger.warning(f'merged: {self.srcs}')
