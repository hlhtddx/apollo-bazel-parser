import re


def get_attr_value(key, attributes, value_type, default_value=None):
    if not attributes or key not in attributes:
        return default_value
    attrib = attributes[key]
    if attrib['explicitlySpecified']:
        return attrib[value_type]
    return default_value


LOC_PATTERN = re.compile(r'/apollo/(.*)/BUILD(:\d+)*')


def normalize_location(location: str):
    match = LOC_PATTERN.match(location)
    if not match:
        return None
    return match[1]


NAME_GLOBAL_NAMESPACE_PATTERN = re.compile(r'/((/\w+)+):(.+)')
NAME_THIRD_PARTY_PATTERN = re.compile('@.+:(.+)')


def normalize_name(name: str):
    m = NAME_GLOBAL_NAMESPACE_PATTERN.match(name)
    if m:
        name_path = m[1].replace('/', '_')
        return '_'.join(('apollo', name_path[1:], m[3]))

    m = NAME_THIRD_PARTY_PATTERN.match(name)
    if m:
        return m[1]
    return name
