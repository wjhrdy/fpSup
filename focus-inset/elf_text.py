"""Extract self-contained .text from one strict ELF32 ARM relocatable object.

This is deliberately not a linker. No relocation is applied and no data section
is mapped. Function offsets retain the ARM ELF Thumb bit, so ``base + offset``
is the callable address when ``base`` is aligned and .text is copied unchanged.
Read-only metadata (for example .ARM.exidx) is validated but not loaded. This
helper does not validate instruction behavior or provide a firmware ABI proof.
"""
from dataclasses import dataclass
from pathlib import Path
import struct
from typing import Dict, Union


class ELFError(ValueError):
    """The object is malformed or needs behavior this extractor does not offer."""


@dataclass(frozen=True)
class TextImage:
    code: bytes
    functions: Dict[str, int]


@dataclass(frozen=True)
class _Section:
    name_offset: int
    kind: int
    flags: int
    address: int
    offset: int
    size: int
    link: int
    info: int
    alignment: int
    entry_size: int


def _require(condition, message):
    if not condition:
        raise ELFError(message)


def _span(data, offset, size, label):
    _require(0 <= offset <= len(data) and 0 <= size <= len(data) - offset,
             label + " exceeds file bounds")
    return data[offset:offset + size]


def _string(table, offset, label):
    _require(0 <= offset < len(table), label + " string offset is out of bounds")
    end = table.find(b"\0", offset)
    _require(end >= 0, label + " string is unterminated")
    try:
        return table[offset:end].decode("ascii")
    except UnicodeDecodeError as exc:
        raise ELFError(label + " string is not ASCII") from exc


def load_text(source: Union[bytes, bytearray, memoryview, str, Path]) -> TextImage:
    """Return .text bytes and named STT_FUNC offsets, or raise ELFError.

    Rejected inputs include extended ELF numbering, program headers, hard-float
    ABI, named undefined symbols, any .text relocation, any writable allocated
    section, and any executable section other than the single .text section.
    Every symbol and relocation entry is checked even in unloaded metadata.
    """
    data = bytes(source) if isinstance(source, (bytes, bytearray, memoryview)) else Path(source).read_bytes()
    _require(len(data) >= 52, "truncated ELF header")
    ident = data[:16]
    _require(ident[:4] == b"\x7fELF", "not ELF")
    _require(ident[4:7] == b"\x01\x01\x01", "requires ELF32 little-endian version 1")
    _require(ident[7] in (0, 97), "unsupported OS ABI")
    _require(ident[8] == 0 and ident[9:] == b"\0" * 7, "unsupported ELF ident flags")
    (kind, machine, version, entry, phoff, shoff, flags, ehsize,
     phentsize, phnum, shentsize, shnum, shstrndx) = struct.unpack_from("<HHIIIIIHHHHHH", data, 16)
    _require(kind == 1 and machine == 40 and version == 1, "requires ARM ET_REL version 1")
    _require(entry == 0 and phoff == 0 and phentsize == 0 and phnum == 0,
             "relocatable object must not contain an entry point or program headers")
    _require(ehsize == 52 and shentsize == 40, "unexpected ELF structure size")
    _require(flags & 0xff000000 == 0x05000000, "requires ARM EABI version 5")
    _require(flags & 0x400 == 0, "hard-float ABI is not supported")
    _require(flags & ~0x05000200 == 0, "unsupported ARM ELF flags")
    _require(0 < shnum < 0xff00 and 0 < shstrndx < shnum, "extended or invalid section numbering")
    _require(shoff >= ehsize and shoff % 4 == 0, "invalid section table offset")
    _span(data, shoff, shnum * 40, "section table")
    sections = [_Section(*struct.unpack_from("<10I", data, shoff + n * 40)) for n in range(shnum)]
    _require(all(v == 0 for v in sections[0].__dict__.values()), "invalid null section")
    occupied = [(0, ehsize, "ELF header"), (shoff, shoff + shnum * 40, "section table")]
    for n, sec in enumerate(sections[1:], 1):
        _require(sec.address == 0, "section %d has a runtime address" % n)
        _require(sec.alignment == 0 or sec.alignment & (sec.alignment - 1) == 0,
                 "section %d has invalid alignment" % n)
        _require(sec.kind != 0, "nonzero section has SHT_NULL type")
        _require(sec.kind in (1, 2, 3, 4, 8, 9, 0x70000001, 0x70000003, 0x6fff4c03),
                 "unsupported section type")
        if sec.kind == 0x6fff4c03:  # LLVM address-significance metadata.
            _require(sec.size == 0, "nonempty LLVM address-significance metadata is unsupported")
        _require(sec.link < shnum, "section %d has invalid link" % n)
        _require(not (sec.flags & 1 and sec.flags & 2), "writable allocated section is unsupported")
        _require(not (sec.flags & 0x800), "compressed section is unsupported")
        if sec.kind != 8:  # SHT_NOBITS has no bytes in the object.
            _span(data, sec.offset, sec.size, "section %d" % n)
            _require(not sec.size or sec.alignment <= 1 or sec.offset % sec.alignment == 0,
                     "section %d file offset is misaligned" % n)
            if sec.size:
                occupied.append((sec.offset, sec.offset + sec.size, "section %d" % n))
        else:
            _require(sec.offset <= len(data), "NOBITS offset exceeds file bounds")
    occupied.sort()
    for first, second in zip(occupied, occupied[1:]):
        _require(first[1] <= second[0], first[2] + " overlaps " + second[2])

    names_section = sections[shstrndx]
    _require(names_section.kind == 3, "section names require SHT_STRTAB")
    names_table = _span(data, names_section.offset, names_section.size, "section names")
    _require(names_table[:1] == b"\0" and names_table[-1:] == b"\0", "invalid section string table")
    names = [_string(names_table, s.name_offset, "section") for s in sections]
    text_indexes = [n for n, name in enumerate(names) if name == ".text"]
    _require(len(text_indexes) == 1, "requires exactly one .text section")
    text_index = text_indexes[0]
    text_section = sections[text_index]
    _require(text_section.kind == 1 and text_section.flags == 6 and text_section.size > 0,
             ".text must be nonempty allocated executable PROGBITS")
    _require(text_section.alignment <= 4, ".text requires stronger alignment than the extraction contract")
    _require(all(n == text_index or not (sec.flags & 4) for n, sec in enumerate(sections)),
             "additional executable section is unsupported")

    symtabs = [n for n, sec in enumerate(sections) if sec.kind == 2]
    _require(len(symtabs) == 1, "requires exactly one symbol table")
    _require(not any(sec.kind == 11 for sec in sections), "dynamic symbol tables are unsupported")
    symbols_section = sections[symtabs[0]]
    _require(symbols_section.entry_size == 16 and symbols_section.size % 16 == 0,
             "invalid symbol table entry size")
    symbol_count = symbols_section.size // 16
    _require(symbol_count > 0 and 1 <= symbols_section.info <= symbol_count, "invalid symbol table local boundary")
    strings_section = sections[symbols_section.link]
    _require(strings_section.kind == 3, "symbol names require SHT_STRTAB")
    strings = _span(data, strings_section.offset, strings_section.size, "symbol names")
    _require(strings[:1] == b"\0" and strings[-1:] == b"\0", "invalid symbol string table")
    functions = {}
    for n in range(symbol_count):
        symbol = struct.unpack_from("<IIIBBH", data, symbols_section.offset + n * 16)
        name_offset, value, size, info, other, index = symbol
        if n == 0:
            _require(symbol == (0, 0, 0, 0, 0, 0), "invalid null symbol")
            continue
        name = _string(strings, name_offset, "symbol")
        symbol_type, binding = info & 15, info >> 4
        _require((binding == 0) == (n < symbols_section.info), "symbol local boundary mismatch")
        _require(other & ~3 == 0, "unsupported symbol visibility bits")
        _require(index != 0, "undefined symbol: " + (name or "<unnamed>"))
        _require(index < shnum or index == 0xfff1, "unsupported symbol section index")
        if index < shnum:
            actual = value & ~1 if symbol_type == 2 else value
            _require(actual <= sections[index].size and size <= sections[index].size - actual,
                     "symbol exceeds section bounds: " + name)
        if symbol_type == 2:
            _require(index == text_index and bool(name) and size > 0, "function must have a nonempty body in .text")
            _require(name not in functions, "duplicate function name: " + name)
            functions[name] = value
    _require(bool(functions), "no named functions in .text")

    for sec in sections:
        if sec.kind not in (4, 9):
            continue
        expected = 12 if sec.kind == 4 else 8
        _require(sec.entry_size == expected and sec.size % expected == 0, "invalid relocation entry size")
        _require(sec.link == symtabs[0] and 0 < sec.info < shnum, "invalid relocation target or symbol table")
        _require(sec.info != text_index, ".text relocation is unsupported; this helper is not a linker")
        for offset in range(sec.offset, sec.offset + sec.size, expected):
            target_offset, info = struct.unpack_from("<II", data, offset)
            _require(target_offset < sections[sec.info].size, "relocation exceeds target section bounds")
            _require(info >> 8 < symbol_count, "relocation symbol index is out of bounds")
    return TextImage(_span(data, text_section.offset, text_section.size, ".text"), functions)
