"""Stateless file conversion commands."""

from ..conversion import convert_workbook
from .common import emit


def convert(args):
    result = convert_workbook(args.input, args.out, force=args.force)
    emit(result, as_json=args.json)
    return 0
