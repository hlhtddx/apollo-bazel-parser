from .cc import parse_cc_rule


def parse_cquery_result(message):
    for target in message.results:
        parse_target(target)


def parse_target(message):
    target = message.target
    type = target.type
    if type == 1:  # RULE
        parse_rule(target)
    elif type == 2:  # SOURCE_FILE
        parse_source_file(target)
    elif type == 3:  # GENERATED_FILE
        parse_generated_file(target)
    elif type == 4:  # PACKAGE_GROUP
        parse_package_group(target)
    elif type == 5:  # ENVIRONMENT_GROUP
        parse_environment(target)
    else:
        raise 1


def parse_rule(message):
    rule = message.rule
    name = rule.name
    rule_class = rule.rule_class
    location = rule.location
    attributes = {}
    for attr in rule.attribute:
        attributes[attr.name] = attr
    # filter
    if rule_class in ('cc_binary', 'cc_library', 'cc_proto_library', 'proto_library'):
        parse_cc_rule(name, rule_class, location, attributes)


def parse_source_file(message):
    pass


def parse_generated_file(message):
    pass


def parse_package_group(message):
    pass


def parse_environment(message):
    pass
