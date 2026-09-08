"""Safe YAML with duplicate-key and expansion limits."""

from ._vendor import yaml
from .common import AssessmentError


class StrictLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self.node_count = 0
        self.depth = 0

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise AssessmentError("YAML aliases are not supported; use explicit values")
        self.node_count += 1
        self.depth += 1
        if self.node_count > 50000 or self.depth > 100:
            raise AssessmentError("YAML exceeds document complexity limits")
        try:
            return super().compose_node(parent, index)
        finally:
            self.depth -= 1

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise AssessmentError(f"YAML keys must be strings at line {key_node.start_mark.line + 1}")
            if key in mapping:
                raise AssessmentError(f"Duplicate YAML key '{key}' at line {key_node.start_mark.line + 1}")
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


# Keep date-looking scalar strings portable through the JSON contracts.
StrictLoader.yaml_implicit_resolvers = {
    key: [(tag, regex) for tag, regex in resolvers if tag != "tag:yaml.org,2002:timestamp"]
    for key, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}


def loads(text, source="<text>"):
    if len(text.encode("utf-8")) > 2 * 1024 * 1024:
        raise AssessmentError(f"YAML exceeds 2 MiB: {source}")
    try:
        value = yaml.load(text, Loader=StrictLoader)
        from .common import canonical
        try:
            canonical(value)
        except (ValueError, TypeError) as exc:
            raise AssessmentError("YAML values must be finite, JSON-compatible data") from exc
        return value
    except yaml.YAMLError as exc:
        raise AssessmentError(f"Invalid YAML {source}: {exc}") from exc


def load(path):
    try:
        if path.stat().st_size > 2 * 1024 * 1024:
            raise AssessmentError(f"YAML exceeds 2 MiB: {path}")
        return loads(path.read_text(encoding="utf-8-sig"), str(path))
    except (OSError, UnicodeError) as exc:
        raise AssessmentError(f"Cannot read {path}: {exc}") from exc
