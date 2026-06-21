"""noisemaker-blender DSL compiler package (lexer/parser/validator/graph port).

Stage-1 (``compile``) mirrors the reference ``shaders/src/lang/index.js``:
``compile(source)`` == lex -> parse -> validate, returning the validated program
(with diagnostics) that the expander consumes.
"""

from .lexer import lex
from .parser import parse, parse_source
from .validator import validate
from .compile import compile
from .transform import replace_effect, list_steps, get_compatible_replacements

__all__ = [
    "lex",
    "parse",
    "parse_source",
    "validate",
    "compile",
    "replace_effect",
    "list_steps",
    "get_compatible_replacements",
]
