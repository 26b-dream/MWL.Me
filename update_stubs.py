from __future__ import annotations

# Standard Library
# StandardLibrary
import inspect
import subprocess

# Common
from common.constants import BASE_DIR
from common.extended_bs4 import ORIGINAL_TAG_FUNCTIONS, ExtendedTag
from common.extended_path import ExtendedPath


def generic_update(stub: ExtendedPath, extended_object: object, functions: list[str], class_string: str) -> None:
    # Convert to a list[str] to make it easier to modify
    stub_lines = stub.read_text().splitlines()

    # Find the line that the tag class is defined
    page_line = 0
    for i, line in enumerate(stub_lines):
        if line == class_string:
            page_line = i + 1
            break

    # Get the functions that where added
    all_functions = dir(extended_object)

    print(f"Adding functions to {class_string}")
    for function in all_functions:
        # If function already exists no modifications needs to be made
        if function in functions:
            continue
        # Create and add signature
        partial_signature = inspect.signature(getattr(extended_object, function))
        stub_lines.insert(page_line, f"    def {function}{partial_signature}: ...")
        print(f"\tAdded: {function}")
    stub_string = "\n".join(stub_lines)

    # Export modifications
    stub.write_text(stub_string)


def update_bs4():
    # Get stub paths
    stub_path = (
        ExtendedPath.home()
        / ".vscode/extensions/ms-python.vscode-pylance-2022.7.30/dist/typeshed-fallback/stubs/beautifulsoup4/bs4"
    )
    typing_path = BASE_DIR / "typings" / "bs4"
    stub = typing_path / "element.pyi"

    # Refresh stubs to be originals
    typing_path.delete()
    stub_path.copy_dir(typing_path)

    generic_update(stub, ExtendedTag, ORIGINAL_TAG_FUNCTIONS, "class Tag(PageElement):")

    stub_content = stub.read_text()

    # A couple of functions use kwargs without a type, just make them Any to get rid of errors
    element_stub_string = stub_content.replace("**kwargs)", "**kwargs: Any)")

    # Export modifications
    stub.write_text(element_stub_string)


if __name__ == "__main__":
    update_bs4()
