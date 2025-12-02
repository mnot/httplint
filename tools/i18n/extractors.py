import ast
from typing import Iterator, Tuple, List
from babel.messages.extract import extract_python


def extract_notes(
    fileobj, keywords, comment_tags, options
) -> Iterator[Tuple[int, str, List[str], List[str]]]:
    """
    Extract messages from Note subclasses in Python source code.

    This looks for classes that inherit from 'Note' or 'HttpField' (or have them in their bases)
    and extracts the strings assigned to '_summary', '_text', or 'description'.

    It also delegates to the standard Python extractor to find other messages.
    """
    # Read content for AST parsing
    content = fileobj.read()
    tree = ast.parse(content)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            # Check if class inherits from Note or HttpField (simple check)
            is_target = False
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in ["Note", "HttpField"]:
                    is_target = True
                    break
                # Handle module.Note or module.HttpField
                if isinstance(base, ast.Attribute) and base.attr in [
                    "Note",
                    "HttpField",
                ]:
                    is_target = True
                    break

            if is_target:
                for item in node.body:
                    if isinstance(item, ast.Assign):
                        for target in item.targets:
                            if isinstance(target, ast.Name) and target.id in [
                                "_summary",
                                "_text",
                                "description",
                            ]:
                                if isinstance(item.value, ast.Constant) and isinstance(
                                    item.value.value, str
                                ):
                                    yield (item.lineno, "_", [item.value.value], [])
                                # Handle multiline strings (which might be parsed differently depending on python version, but usually Constant)

    # Delegate to standard python extractor
    fileobj.seek(0)

    # Merge keywords from options
    extra_keywords = options.get("keywords", [])
    if isinstance(extra_keywords, str):
        extra_keywords = extra_keywords.split()

    all_keywords = list(keywords) + extra_keywords

    # We need to pass a container that supports 'in' to extract_python.
    # A list is fine.

    for lineno, funcname, messages, comments in extract_python(
        fileobj, all_keywords, comment_tags, options
    ):
        if funcname in extra_keywords:
            funcname = None
        yield (lineno, funcname, messages, comments)
