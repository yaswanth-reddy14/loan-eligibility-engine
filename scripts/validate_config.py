from pathlib import Path

import yaml


class CloudLoader(yaml.SafeLoader):
    pass


def intrinsic(loader, suffix, node):
    if isinstance(node, yaml.ScalarNode):
        return {suffix: loader.construct_scalar(node)}
    if isinstance(node, yaml.SequenceNode):
        return {suffix: loader.construct_sequence(node)}
    return {suffix: loader.construct_mapping(node)}


CloudLoader.add_multi_constructor("!", intrinsic)

# Runtime-owned names from the Lambda environment-variable reference. Do not
# reject all AWS_* names: SDK configuration such as AWS_MAX_ATTEMPTS is valid.
RESERVED_ENV = {
    "_HANDLER",
    "_X_AMZN_TRACE_ID",
    "AWS_DEFAULT_REGION",
    "AWS_REGION",
    "AWS_EXECUTION_ENV",
    "AWS_LAMBDA_FUNCTION_NAME",
    "AWS_LAMBDA_FUNCTION_MEMORY_SIZE",
    "AWS_LAMBDA_FUNCTION_VERSION",
    "AWS_LAMBDA_INITIALIZATION_TYPE",
    "AWS_LAMBDA_LOG_GROUP_NAME",
    "AWS_LAMBDA_LOG_STREAM_NAME",
    "AWS_ACCESS_KEY",
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_LAMBDA_RUNTIME_API",
    "LAMBDA_TASK_ROOT",
    "LAMBDA_RUNTIME_DIR",
}


def validate(value):
    provider_env = value["provider"].get("environment", {})
    for name, function in value.get("functions", {}).items():
        keys = set(provider_env) | set(function.get("environment", {}))
        reserved = keys & RESERVED_ENV
        if reserved:
            raise ValueError(
                f"Reserved Lambda environment variables in {name}: {', '.join(sorted(reserved))}"
            )
    resources = value["resources"]["Resources"]
    assert value["provider"]["runtime"] == "python3.12"
    assert resources["IngestionQueue"]["Properties"]["VisibilityTimeout"] >= 6 * value["provider"]["timeout"]
    assert (
        value["functions"]["ingest"]["events"][0]["sqs"]["functionResponseType"] == "ReportBatchItemFailures"
    )
    assert all(resources["UploadBucket"]["Properties"]["PublicAccessBlockConfiguration"].values())


def main():
    value = yaml.load(Path("serverless.yml").read_text(), Loader=CloudLoader)
    validate(value)
    print(
        "Serverless YAML and critical static invariants passed. AWS/Serverless resolution remains unverified."
    )


if __name__ == "__main__":
    main()
