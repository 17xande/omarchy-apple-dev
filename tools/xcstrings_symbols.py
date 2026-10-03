"""`xcstringstool generate-symbols --language swift`: one LocalizedStringResource symbol per manually
managed key, in the shape Xcode 27's xcstringstool writes."""
import re

SPEC = re.compile(r"%(\d+\$)?([-+ #0]*\d*(?:\.\d+)?)(hh|h|ll|l|q|z|t|j|L)?([@dDiuUxXoOfeEgGcCsSpaA])")


def swift_type(length, conversion):
    """Swift parameter type for one format specifier, as Xcode 27 picks it (%d Int32, %lld Int,
    %u UInt32, %f Float, %@ String were checked against it; the other rows follow C's sizes)."""
    if conversion in "dDi":
        return {"hh": "Int8", "h": "Int16", None: "Int32"}.get(length, "Int")
    if conversion in "uUxXoO":
        return {"hh": "UInt8", "h": "UInt16", None: "UInt32"}.get(length, "UInt")
    if conversion in "feEgGaA":
        return "Float" if length is None else "Double"
    return {"c": "CChar", "C": "UInt16", "s": "UnsafePointer<CChar>", "S": "UnsafePointer<UInt16>",
            "p": "UnsafeRawPointer"}.get(conversion, "String")

HEADER = """// 
// GeneratedStringSymbols_{stem}.swift
// Auto-Generated symbols for localized strings defined in “{name}”.
// 

import Foundation

#if SWIFT_PACKAGE
private nonisolated let resourceBundle = Foundation.Bundle.module
@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)
private nonisolated let resourceBundleDescription = LocalizedStringResource.BundleDescription.atURL(resourceBundle.bundleURL)
#else

private class ResourceBundleClass {{}}
@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)
private nonisolated let resourceBundleDescription = LocalizedStringResource.BundleDescription.forClass(ResourceBundleClass.self)
#endif
"""


def camel(words):
    out = []
    for i, w in enumerate(words):
        if w.isupper():
            w = w.capitalize()
        out.append(w[0].lower() + w[1:] if i == 0 else w[0].upper() + w[1:])
    return "".join(out)


def identifier(key):
    text = SPEC.sub(" ", key).replace("'", "").replace("’", "")
    name = camel(re.findall(r"[A-Za-z0-9]+", text)) or "string"
    return "_" + name if name[0].isdigit() else name


def swift_literal(s):
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")


def arguments(key, locs, source):
    """[(label or None, variable, swift type, specifier)] for the key's format specifiers. Substitution
    names label their arguments, from the source language or else the first language that has them."""
    labels = {}
    order = [source] + sorted(lang for lang in locs if lang != source)
    subs = next((locs[lang]["substitutions"] for lang in order if "substitutions" in locs.get(lang, {})), {})
    for pos, (name, sub) in enumerate(subs.items(), start=1):
        labels[sub.get("argNum", pos)] = camel(re.findall(r"[A-Za-z0-9]+", name))
    args = []
    for n, m in enumerate(SPEC.finditer(key.replace("%%", "")), start=1):
        label = labels.get(n)
        spec = "%" + m.group(2) + (m.group(3) or "") + m.group(4)
        args.append((label, label or f"arg{n}", swift_type(m.group(3), m.group(4)), spec))
    return args


def symbol(key, entry, stem, source):
    doc = []
    if entry.get("comment"):
        first, *rest = entry["comment"].split("\n")
        doc += [f"     {first}", *rest, "     "]
    doc.append(f"     Localized string for key “{key}” in table “{stem}.xcstrings”.")
    head = ["    /**", *doc, "     */"]
    name, lit = identifier(key), swift_literal(key)
    args = arguments(key, entry.get("localizations") or {}, source)
    if not args:
        return "\n".join([
            *head,
            f"    static var {name}: LocalizedStringResource {{",
            f'        LocalizedStringResource("{lit}", table: "{stem}", bundle: resourceBundleDescription)',
            "    }",
        ])
    params = ", ".join(f"{var}: {typ}" if label else f"_ {var}: {typ}" for label, var, typ, _ in args)
    default = "".join(f"\\({var})" if typ == "String" else f'\\({var}, specifier: "{spec}")'
                      for _, var, typ, spec in args)
    return "\n".join([
        *head,
        f"    static func {name}({params}) -> LocalizedStringResource {{",
        f'        LocalizedStringResource("{lit}", defaultValue: "{default}", table: "{stem}", '
        "bundle: resourceBundleDescription)",
        "    }",
    ])


def swift_symbols(catalog, name, stem):
    source = catalog["sourceLanguage"]
    strings = catalog.get("strings", {})
    manual = [(k, strings[k]) for k in sorted(strings) if strings[k].get("extractionState") == "manual"]
    text = HEADER.format(stem=stem, name=name)
    if manual:
        body = "\n\n".join(symbol(k, e, stem, source) for k, e in manual)
        text += ("\n@available(macOS 13, iOS 16, tvOS 16, watchOS 9, *)\n"
                 f"nonisolated extension LocalizedStringResource {{\n{body}\n}}")
    return text
