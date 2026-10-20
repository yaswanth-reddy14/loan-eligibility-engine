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


def main():
    value = yaml.load(Path("serverless.yml").read_text(), Loader=CloudLoader)
    resources = value["resources"]["Resources"]
    assert value["provider"]["runtime"] == "python3.12"
    assert resources["IngestionQueue"]["Properties"]["VisibilityTimeout"] >= 6 * value["provider"]["timeout"]
    assert (
        value["functions"]["ingest"]["events"][0]["sqs"]["functionResponseType"] == "ReportBatchItemFailures"
    )
    assert all(resources["UploadBucket"]["Properties"]["PublicAccessBlockConfiguration"].values())
    print(
        "Serverless YAML and critical static invariants passed. AWS/Serverless resolution remains unverified."
    )


if __name__ == "__main__":
    main()
