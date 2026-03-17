from typing import Tuple, Dict, Any

import yaml


def build_app_name(cluster: str, namespace: str, name: str, resource: str) -> str:
    return f"{cluster}-{namespace}-{resource}-{name}"


def break_app_name(app_name: str) -> str:
    split = app_name.split("-")   
    return split[0], split[1], split[3]


def _normalize(data):
    if isinstance(data, dict):
        return {k: _normalize(v) for k, v in sorted(data.items())}
    if isinstance(data, list):
        return sorted((_normalize(i) for i in data), key=lambda x: str(x))
    return data


def yaml_data_equals(yaml_data_1, yaml_data_2) -> bool:
    if isinstance(yaml_data_1, str):
        yaml_data_1 = yaml.safe_load(yaml_data_1)
    if isinstance(yaml_data_2, str):
        yaml_data_2 = yaml.safe_load(yaml_data_2)
    return _normalize(yaml_data_1) == _normalize(yaml_data_2)


def parse_payload(payload) -> Tuple[str, str, str, str, str, Dict[str, Any]]:
    data = payload.model_dump(mode="json", exclude_none=True)
    metadata = data.pop("metadata")
    namespace = metadata.pop("namespace")
    app_name = metadata.pop("name")
    cluster = metadata.pop("cluster")
    paas_labels = metadata.pop("paasLabels")
    version = metadata.pop("version")

    values = dict(data.get("values") or {})
    values["paasLabels"] = paas_labels
    values["chartVersion"] = version
    secrets = data.get("secrets") or values.get("secrets") or {}

    if "secrets" in values:
        values.pop("secrets", None)

    yaml_data = yaml.safe_dump(values, sort_keys=False)
    path = f"/{cluster}/{namespace}/{app_name}.yaml"

    return path, yaml_data, cluster, namespace, app_name, secrets


def filter_secret_payload(secrets: Dict[str, Any]) -> Dict[str, Any]:
    """Remove entries without concrete values so we avoid empty Vault writes."""

    def _has_value(value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, str):
            return bool(value.strip())
        if isinstance(value, dict):
            return any(_has_value(v) for v in value.values())
        if isinstance(value, (list, tuple, set)):
            return any(_has_value(v) for v in value)
        return True

    def _clean(value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str):
            return value if value.strip() else None
        if isinstance(value, dict):
            cleaned = {k: _clean(v) for k, v in value.items()}
            compacted = {k: v for k, v in cleaned.items() if _has_value(v)}
            return compacted or None
        if isinstance(value, list):
            cleaned_list = [_clean(item) for item in value]
            compacted_list = [item for item in cleaned_list if _has_value(item)]
            return compacted_list or None
        if isinstance(value, tuple):
            cleaned_tuple = tuple(_clean(item) for item in value)
            compacted_tuple = tuple(item for item in cleaned_tuple if _has_value(item))
            return compacted_tuple or None
        if isinstance(value, set):
            cleaned_set = {_clean(item) for item in value}
            compacted_set = {item for item in cleaned_set if _has_value(item)}
            return compacted_set or None
        return value

    if not secrets:
        return {}

    cleaned_secrets = {key: _clean(value) for key, value in secrets.items()}
    return {key: value for key, value in cleaned_secrets.items() if _has_value(value)}
