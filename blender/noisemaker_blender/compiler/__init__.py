"""noisemaker-blender DSL compiler package (lexer/parser/validator/graph port).

Stage-1 (``compile``) mirrors the reference ``shaders/src/lang/index.js``:
``compile(source)`` == lex -> parse -> validate, returning the validated program
(with diagnostics) that the expander consumes.

Stage-2 (``expand``) mirrors ``shaders/src/runtime/expander.js``: it turns the
validated program's logical graph (``plans``) into a render graph
(``{passes, programs, textureSpecs, renderSurface}``). Together ``expand(compile(
source))`` is the front half of the reference ``compileGraph`` pipeline (the
resource-allocation + assembly stage that consumes ``passes`` comes next).
"""

from .lexer import lex
from .parser import parse, parse_source
from .validator import validate
from .compile import compile
from .transform import replace_effect, list_steps, get_compatible_replacements
from .expander import expand
from .palette_expansion import expand_palette

__all__ = [
    "lex",
    "parse",
    "parse_source",
    "validate",
    "compile",
    "replace_effect",
    "list_steps",
    "get_compatible_replacements",
    "expand",
    "expand_palette",
]
