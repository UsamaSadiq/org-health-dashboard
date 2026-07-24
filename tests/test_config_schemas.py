from dashboard.lib.config import read_config_file
from dashboard.lib.schema import validate_config_data


def test_openedx_config_files_validate_against_schemas():
    config_names = [
        "data_source",
        "check_groups",
        "check_descriptions",
        "check_candidates",
        "remediation",
        "pr_templates",
        "scoring",
        "tiers",
        "attention_rules",
        "strings",
        "org_branding",
    ]

    for name in config_names:
        payload = read_config_file(f"config/openedx/{name}.yaml")
        assert validate_config_data(name, payload, strict=True)


def test_feature_flags_config_validates_against_schema():
    payload = read_config_file("config/feature_flags.yaml")
    assert validate_config_data("feature_flags", payload, strict=True)
