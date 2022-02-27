from bazel import normalize_location, normalize_name


class Module(object):
    def __init__(self, name, location: str, normal_name: str):
        self.name = name
        self.path = normalize_location(location)
        self.normal_name = normal_name if normal_name else normalize_name(name)
        self.location = location

    def post_load(self, modules):
        pass

    def parse(self, bp_file):
        pass

    def output(self, bp_file):
        pass
