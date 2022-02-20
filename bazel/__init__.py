import re


def get_attr_boolean_value(key, attributes, default_value):
    if attributes and key in attributes:
        return attributes[key].boolean_value
    return default_value


def get_attr_string_value(key, attributes, default_value):
    if attributes and key in attributes:
        return attributes[key].string_value
    return default_value


def get_attr_string_list_value(key, attributes, default_value):

    if attributes and key in attributes:
        return list(attributes[key].string_list_value)
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
